"""Render docs/demo/transcript.json as chat pages and, optionally, PNG screenshots.

Usage: python -m scripts.render_demo [--screenshots]      (screenshots need Microsoft Edge)
Writes docs/demo/chat-customer.html and chat-admin.html (the chats as they end) plus one page per snapshot
marked in the transcript (docs/demo/NN-name.html). The pages only lay out what the bot really sent: edits
are applied in place, button taps and toasts leave no trace in the history, and a reply keyboard is docked
at the bottom while it is active. See scripts/capture_demo.py for how the transcript is recorded.
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "docs" / "demo"
SHOTS = ROOT / "docs" / "screenshots"
EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")

ALLOWED = {"b": "b", "strong": "b", "i": "i", "em": "i", "u": "u", "s": "s", "code": "code", "pre": "pre"}

CSS = """
:root{--bg:#dfe6ee;--bot:#ffffff;--me:#d9f2c4;--ink:#16202a;--muted:#6b7a89;--btn:#e4ebf3;--btn-ink:#26527a;--head:#f7f9fb;--line:#c9d3de}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.4 "Segoe UI",system-ui,sans-serif}
.phone{width:420px;margin:0 0 0 10px;min-height:420px;background:var(--bg);display:flex;flex-direction:column}
.head{display:flex;align-items:center;gap:12px;padding:10px 14px;background:var(--head);border-bottom:1px solid var(--line)}
.avatar{width:40px;height:40px;border-radius:50%;background:#3d7ea6;color:#fff;font-weight:600;display:flex;align-items:center;justify-content:center;letter-spacing:.5px}
.title{font-weight:600}.sub{font-size:12.5px;color:var(--muted)}
.feed{flex:1;padding:12px 10px 14px;display:flex;flex-direction:column;justify-content:flex-end;gap:6px}
.item{display:flex;flex-direction:column;max-width:88%}
.item.bot{align-self:flex-start;align-items:flex-start}
.item.me{align-self:flex-end;align-items:flex-end}
.bubble{border-radius:14px;padding:7px 11px 6px;box-shadow:0 1px 1px rgba(0,0,0,.10);white-space:pre-wrap;overflow-wrap:anywhere}
.bot .bubble{background:var(--bot);border-bottom-left-radius:4px}
.me .bubble{background:var(--me);border-bottom-right-radius:4px}
.meta{display:block;text-align:right;font-size:11px;color:var(--muted);margin-top:2px;white-space:normal}
code,pre{font-family:Consolas,monospace;background:#eef2f6;border-radius:4px;padding:0 3px}
.photo{width:100%;min-width:250px;aspect-ratio:12/5;border-radius:9px;margin:-2px 0 6px;background:linear-gradient(135deg,#cfdde8,#e8eef3);color:#6b7a89;display:flex;align-items:center;justify-content:center;font-size:13px}
.kb{display:flex;flex-direction:column;gap:4px;margin-top:4px;width:100%}
.row{display:flex;gap:4px}
.btn{flex:1;min-width:0;text-align:center;background:var(--btn);color:var(--btn-ink);border-radius:9px;padding:7px 8px;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dock{background:var(--head);border-top:1px solid var(--line);padding:8px 10px 10px}
.dock .input{background:#fff;border:1px solid var(--line);border-radius:18px;padding:7px 14px;color:var(--muted)}
.dock .kb{margin:0}
.dock .btn{background:#fff;color:var(--ink);border:1px solid var(--line);padding:10px 8px}
"""

JS = "document.body.dataset.h=Math.ceil(document.querySelector('.phone').getBoundingClientRect().height);"


class SafeHtml(HTMLParser):
    """Keeps Telegram's HTML subset (b, i, u, s, code, pre) and escapes everything else."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ALLOWED:
            self.out.append(f"<{ALLOWED[tag]}>")
            self.open.append(ALLOWED[tag])
        else:
            self.out.append(escape(self.get_starttag_text() or ""))

    def handle_endtag(self, tag):
        if tag in ALLOWED and ALLOWED[tag] in self.open:
            self.open.remove(ALLOWED[tag])
            self.out.append(f"</{ALLOWED[tag]}>")
        else:
            self.out.append(escape(f"</{tag}>"))

    def handle_data(self, data):
        self.out.append(escape(data))

    def result(self) -> str:
        return "".join(self.out) + "".join(f"</{t}>" for t in reversed(self.open))


def telegram_html(text: str) -> str:
    parser = SafeHtml()
    parser.feed(text)
    parser.close()
    return parser.result()


def clock(ts: str) -> str:
    return ts[:5]


def keyboard_html(rows: list[list[str]] | None) -> str:
    if not rows:
        return ""
    body = "".join(
        '<div class="row">' + "".join(f'<div class="btn">{escape(b)}</div>' for b in row) + "</div>" for row in rows
    )
    return f'<div class="kb">{body}</div>'


class Chat:
    """The state of one chat: messages (edited in place) and the active reply keyboard."""

    def __init__(self) -> None:
        self.items: list[dict] = []
        self.by_id: dict[int, dict] = {}
        self.reply_keyboard: list[list[str]] | None = None

    def apply(self, e: dict) -> None:
        kind = e["type"]
        if kind == "user_text":
            self.items.append({"side": "me", "text": e["text"], "ts": e["ts"]})
        elif kind in ("send", "photo"):
            item = {"side": "bot", "text": e["text"], "ts": e["ts"], "keyboard": e.get("keyboard"),
                    "photo": kind == "photo", "edited": False}
            self.items.append(item)
            self.by_id[e["message_id"]] = item
            if e.get("reply_keyboard"):
                self.reply_keyboard = e["reply_keyboard"]
            elif e.get("reply_keyboard_removed"):
                self.reply_keyboard = None
        elif kind == "edit" and e["message_id"] in self.by_id:
            item = self.by_id[e["message_id"]]
            item.update(text=e["text"], keyboard=e.get("keyboard"), edited=True, edit_ts=e["ts"])
        elif kind == "edit_markup" and e["message_id"] in self.by_id:
            self.by_id[e["message_id"]]["keyboard"] = e.get("keyboard")

    def view(self, last: int | None) -> tuple[list[dict], list[list[str]] | None]:
        items = copy.deepcopy(self.items if last is None else self.items[-last:])
        return items, self.reply_keyboard


def item_html(item: dict) -> str:
    if item["side"] == "me":
        return (f'<div class="item me"><div class="bubble">{escape(item["text"])}'
                f'<span class="meta">{clock(item["ts"])}</span></div></div>')
    photo = '<div class="photo">Product photo</div>' if item["photo"] else ""
    meta = f'edited {clock(item["edit_ts"])}' if item["edited"] else clock(item["ts"])
    return (
        f'<div class="item bot"><div class="bubble">{photo}{telegram_html(item["text"])}'
        f'<span class="meta">{meta}</span></div>{keyboard_html(item["keyboard"])}</div>'
    )


def initials(name: str) -> str:
    return "".join(w[0] for w in [w for w in re.split(r"[^A-Za-z]+", name) if w][:2]).upper()


def page(shop: str, who: str, items: list[dict], reply_keyboard: list[list[str]] | None) -> str:
    feed = "\n".join(item_html(i) for i in items)
    dock = keyboard_html(reply_keyboard) or '<div class="input">Message</div>'
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(shop)} - {escape(who)}</title><style>{CSS}</style></head><body>"
        '<div class="phone">'
        f'<div class="head"><div class="avatar">{initials(shop)}</div>'
        f'<div><div class="title">{escape(shop)}</div><div class="sub">bot &middot; {escape(who)}</div></div></div>'
        f'<div class="feed">\n{feed}\n</div><div class="dock">{dock}</div></div><script>{JS}</script></body></html>\n'
    )


def render() -> list[Path]:
    data = json.loads((DEMO / "transcript.json").read_text(encoding="utf-8"))
    shop = data["shop_name"]
    ids = {u["id"]: role for role, u in data["users"].items()}
    who = {"customer": "customer view", "admin": "shop owner view"}
    chats = {role: Chat() for role in who}
    snapshots: list[Path] = []
    for e in data["events"]:
        role = ids.get(e["chat"])
        if role is None:
            continue
        if e["type"] == "snapshot":
            items, reply_keyboard = chats[role].view(e["last"])
            path = DEMO / f"{len(snapshots) + 1:02d}-{e['name']}.html"
            path.write_text(page(shop, who[role], items, reply_keyboard), encoding="utf-8")
            snapshots.append(path)
        else:
            chats[role].apply(e)
    for role, chat in chats.items():
        items, reply_keyboard = chat.view(None)
        (DEMO / f"chat-{role}.html").write_text(page(shop, who[role], items, reply_keyboard), encoding="utf-8")
    return snapshots


def edge(*args: str) -> str:
    proc = subprocess.run(
        [str(EDGE), "--headless=new", "--disable-gpu", "--hide-scrollbars", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    return proc.stdout


def screenshots(pages: list[Path]) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    for path in pages:
        url = path.as_uri()
        match = re.search(r'data-h="(\d+)"', edge("--dump-dom", "--window-size=440,800", url))
        if match is None:
            raise RuntimeError(f"could not measure {url}")
        out = SHOTS / f"{path.stem}.png"
        edge(f"--window-size=440,{int(match.group(1)) + 2}", f"--screenshot={out}", url)
        print(f"Wrote {out.relative_to(ROOT)}")


def main() -> None:
    pages = render()
    print(f"Wrote docs/demo/chat-customer.html, chat-admin.html and {len(pages)} snapshot pages")
    if "--screenshots" in sys.argv:
        screenshots(pages)


if __name__ == "__main__":
    main()

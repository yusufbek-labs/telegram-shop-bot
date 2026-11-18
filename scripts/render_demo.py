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
:root{--bg:#0e1621;--head:#17212b;--bot:#182533;--me:#2b5278;--ink:#e8edf2;--muted:#7f91a4;--btn:#1b2733;--line:#0a1119}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14.5px/1.38 "Segoe UI","Segoe UI Emoji",system-ui,sans-serif}
.phone{width:420px;margin:0 0 0 10px;min-height:420px;background:var(--bg);display:flex;flex-direction:column}
.head{display:flex;align-items:center;gap:10px;padding:8px 14px 8px 10px;background:var(--head);border-bottom:1px solid var(--line)}
.head svg{flex:none;fill:none;stroke:var(--muted);stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.pill{background:#2f4152;color:#dfe7ee;border-radius:10px;padding:0 7px;font-size:12px;font-weight:600;line-height:18px;margin-left:-4px}
.avatar{flex:none;width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#4aa3e0,#2a6fb5);color:#fff;font-weight:600;font-size:16px;display:flex;align-items:center;justify-content:center}
.who{flex:1;min-width:0}
.title{font-weight:700;color:#fff;line-height:1.25}.sub{font-size:13px;color:var(--muted);line-height:1.2}
.feed{flex:1;padding:10px 12px 12px;display:flex;flex-direction:column;justify-content:flex-end;gap:5px}
.item{display:flex;flex-direction:column;max-width:90%;gap:4px}
.item.bot{align-self:flex-start}
.item.me{align-self:flex-end}
.bubble{border-radius:12px;padding:6px 10px 5px;white-space:pre-wrap;overflow-wrap:anywhere}
.bot .bubble{background:var(--bot);border-bottom-left-radius:6px}
.me .bubble{background:var(--me);color:#fff;border-bottom-right-radius:6px}
.meta{display:flex;justify-content:flex-end;align-items:center;gap:3px;font-size:11.5px;color:var(--muted);margin-top:1px;white-space:normal}
.me .meta{color:#9fc1e4}
.meta svg{fill:none;stroke:#9fc1e4;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
b{font-weight:700;color:#fff}
code,pre{font-family:Consolas,monospace;color:#8fc7f5;background:rgba(255,255,255,.07);border-radius:4px;padding:0 3px}
.photo{width:100%;min-width:250px;aspect-ratio:12/5;border-radius:8px;margin:1px 0 6px;background:linear-gradient(135deg,#1b2b3b,#2a4057 55%,#1d3042);color:#6f8397;display:flex;align-items:center;justify-content:center;font-size:13px}
.kb{display:flex;flex-direction:column;gap:3px;width:0;min-width:100%}
.row{display:flex;gap:3px}
.btn{flex:1;min-width:0;text-align:center;background:var(--btn);color:#fff;font-weight:600;border-radius:9px;padding:7px 8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dock{background:var(--head);border-top:1px solid var(--line);padding:8px 10px 10px}
.dock .input{display:flex;align-items:center;gap:10px;color:var(--muted);padding:4px 4px}
.dock .input svg{fill:none;stroke:var(--muted);stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.dock .input span{flex:1}
.mono{font-family:"Segoe UI Symbol",sans-serif;color:#6c7883;font-weight:400;font-size:17px;line-height:1}
.dock .kb{width:100%}
.dock .btn{background:#222f3d;padding:11px 8px}
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


BACK = '<svg width="24" height="24" viewBox="0 0 24 24"><path d="M19 12H5M11 18l-6-6 6-6"/></svg>'
SEARCH = '<svg width="22" height="22" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>'
DOTS = ('<svg width="22" height="22" viewBox="0 0 24 24" style="fill:#7f91a4;stroke:none">'
        '<circle cx="12" cy="5" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="12" cy="19" r="1.7"/></svg>')
CHECKS = ('<svg width="18" height="11" viewBox="0 0 18 11"><path d="M1 5.8l3.2 3.2L10 1.8"/>'
          '<path d="M6.2 8.6l.4.4L13.2 1.8"/></svg>')
CLIP = ('<svg width="24" height="24" viewBox="0 0 24 24"><path d="M20 11.5l-7.8 7.8a4.5 4.5 0 0 1-6.4-6.4l8-8a3 3 0 0 1 4.3'
        ' 4.3l-8 8a1.5 1.5 0 0 1-2.1-2.1l7.3-7.3"/></svg>')


def clock(ts: str) -> str:
    return ts[:5]


def button_label(text: str) -> str:
    """Windows draws these symbols as coloured emoji; the Telegram client shows them as muted grey glyphs."""
    return re.sub(r"[\u2796\u2795\u2716]\ufe0f?", lambda m: f'<span class="mono">{m.group(0)[0]}</span>', escape(text))


def keyboard_html(rows: list[list[str]] | None) -> str:
    if not rows:
        return ""
    body = "".join(
        '<div class="row">' + "".join(f'<div class="btn">{button_label(b)}</div>' for b in row) + "</div>" for row in rows
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
        elif kind == "user_photo":
            self.items.append({"side": "me", "text": "", "ts": e["ts"], "photo": "Payment receipt"})
        elif kind in ("send", "photo"):
            item = {"side": "bot", "text": e["text"], "ts": e["ts"], "keyboard": e.get("keyboard"),
                    "photo": photo_label(e["photo"]) if kind == "photo" else None, "edited": False}
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


def photo_label(photo: str) -> str:
    """Product cards send an image URL; anything else is a Telegram file_id, i.e. an uploaded receipt."""
    return "Product photo" if photo.startswith("http") else "Payment receipt"


def item_html(item: dict) -> str:
    photo = f'<div class="photo">{item["photo"]}</div>' if item.get("photo") else ""
    if item["side"] == "me":
        return (f'<div class="item me"><div class="bubble">{photo}{escape(item["text"])}'
                f'<span class="meta">{clock(item["ts"])}{CHECKS}</span></div></div>')
    meta = f'edited {clock(item["edit_ts"])}' if item["edited"] else clock(item["ts"])
    return (
        f'<div class="item bot"><div class="bubble">{photo}{telegram_html(item["text"])}'
        f'<span class="meta">{meta}</span></div>{keyboard_html(item["keyboard"])}</div>'
    )


def initials(name: str) -> str:
    return "".join(w[0] for w in [w for w in re.split(r"[^A-Za-z]+", name) if w][:2]).upper()


def page(shop: str, who: str, items: list[dict], reply_keyboard: list[list[str]] | None) -> str:
    feed = "\n".join(item_html(i) for i in items)
    dock = keyboard_html(reply_keyboard) or '<div class="input"><span>Message</span>' + CLIP + '</div>'
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(shop)} - {escape(who)}</title><style>{CSS}</style></head><body>"
        '<div class="phone">'
        f'<div class="head">{BACK}<span class="pill">2</span><div class="avatar">{initials(shop)}</div>'
        f'<div class="who"><div class="title">{escape(shop)}</div><div class="sub">bot</div></div>{SEARCH}{DOTS}</div>'
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

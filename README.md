# Telegram Shop Bot

A ready-to-run Telegram shop: customers browse a catalog, fill a cart and check out inside the chat, and the shop owner manages orders, products, stats and announcements from the same chat. English and Russian are built in.

> **Portfolio project.** This is a demonstration build with a small fictional catalog ("Maple & Pine Goods"). It has not been used by real customers and makes no claims about sales or users. It has been verified with an automated test suite; a run against the live Telegram service has not been done yet (see [Live demo screenshots](#live-demo-screenshots)).

![Test results](docs/test-results.png)

*Real output of `python -m pytest -q` (194 tests, no network, no bot token needed). Regenerate with `python -m scripts.make_test_image`.*

---

## What it does (for the shop owner)

**Your customers** open the bot and tap through a menu: pick a category, see product cards with price and description (and a photo, if you add an image link), add items to a cart, change quantities, and check out by entering name, phone and delivery address, then choosing cash or card on delivery. They get an order confirmation, and a message every time you change the order status.

**You (the admin)** get every new order in your own Telegram chat with buttons to move it from New to Confirmed, Shipped, Delivered or Cancelled. The bot only offers steps that make sense (a delivered order cannot be cancelled by mistake). You can also list orders by status, switch products on or off, add and edit products by answering a few questions, see today's and the last 7 days' orders and revenue, and send an announcement to everyone who started the bot, with a preview and confirmation first.

### Feature list

| Area | Included |
|---|---|
| Customer menu | `/start` main menu with inline buttons, help, "My orders" |
| Catalog | Categories, product cards (name, price, description, optional image URL) |
| Cart | Add, remove, change quantity, running total, clear |
| Checkout | Step-by-step form (name, phone, address, payment), summary and confirmation, cash or card on delivery |
| Notifications | New orders pushed to all admins; customers notified on every status change |
| Order workflow | `new -> confirmed -> shipped -> delivered`, cancel allowed until delivered; invalid jumps are refused |
| Admin tools | `/orders` (filter by status), `/products` (on/off toggle), `/add_product`, `/edit_product`, `/stats`, `/broadcast` |
| Broadcast | Preview and confirm step, throttled to stay under Telegram's limits, honours flood-control replies, remembers users who blocked the bot |
| Languages | English and Russian, picked from the user's Telegram language, `/language` to switch |
| Robustness | Unknown text, commands, stale buttons and invalid form input get friendly replies; errors are logged, never crash polling |
| Storage | SQLite (single file), money stored in integer cents |

### Not included (by design, see [How to extend](#how-to-extend))
Online card payments, stock counts, discounts, multiple shops, a web dashboard. FSM state is kept in memory, so a half-finished checkout is lost if the bot restarts (the cart and orders are safe in the database).

---

## Quick start (3 steps)

You need Python 3.11+ (developed on 3.12).

1. **Get a token.** In Telegram open [@BotFather](https://t.me/BotFather), send `/newbot`, follow the prompts, copy the token. To find your own numeric Telegram id, message [@userinfobot](https://t.me/userinfobot).
2. **Configure.** Copy `.env.example` to `.env` (`copy .env.example .env` on Windows, `cp .env.example .env` elsewhere) and set `BOT_TOKEN` and `ADMIN_IDS` (your id).
3. **Run.**
   ```
   python run.py
   ```
   That one command creates a virtual environment, installs dependencies, loads the demo catalog on first start and launches the bot. Open your bot in Telegram and send `/start`.

**With Docker** (instead of step 3): `docker compose up -d --build`. The database is kept in `./data`.

> The Dockerfile and compose file were written but **not built or run** on the machine this project was developed on (the Docker daemon was not running). They are short and standard, but treat them as untested until you try them.

Admins must press Start in the bot once, otherwise Telegram will not let the bot message them.

---

## Admin guide

Admins are the Telegram ids in `ADMIN_IDS` (comma-separated). Everyone else is a customer; admin commands answer them with "no permission". Admins see an extended command menu in Telegram.

| Command | What it does |
|---|---|
| New-order message | Arrives automatically. Tap a status button to move the order forward; the customer is notified. Buttons shown are only the allowed next steps. |
| `/orders` | Pick a status filter (or `/orders shipped`, `/orders all`), tap an order to open it and change its status. Shows the latest 10 per filter. |
| `/products` | Lists all products. Tap a product name to show or hide it in the shop; tap Edit to change it. |
| `/add_product` | Choose a category, then send name, price (`12.50`), description and an image URL (or `-` to skip), then confirm. |
| `/edit_product` | Pick a product and a field (name, price, description, image) and send the new value. Existing orders keep the old price. |
| `/stats` | Orders and revenue for today and for the last 7 days (cancelled orders excluded). "Today" follows `TIMEZONE`. |
| `/broadcast` | Send a message, review the preview, confirm. You get a report: sent, blocked, failed. |
| `/cancel` | Abort any multi-step form. |

Order statuses: `new` can become `confirmed` or `cancelled`; `confirmed` can become `shipped` or `cancelled`; `shipped` can become `delivered` or `cancelled`; `delivered` and `cancelled` are final.

Settings (in `.env`): `SHOP_NAME`, `CURRENCY_SYMBOL`, `TIMEZONE`, `DB_PATH`, `LOG_LEVEL`, `BROADCAST_RATE` (messages per second, capped at 30). Product names and descriptions are entered in one language by the admin; category names and all bot texts are bilingual.

To replace the demo catalog: edit `scripts/seed.py` and run `python -m scripts.seed --force` (this wipes products and categories, keeps orders and users), or delete `data/shop.db` and start again.

---

## Live demo screenshots

*Chat screenshots will be added here after a run with a real bot token.* They are intentionally not mocked up: everything on this page that is shown as evidence (the test results above) is real output.

---

## For developers

### Stack
Python 3.12, [aiogram 3](https://docs.aiogram.dev/) (polling, FSM, typed callback data), SQLAlchemy 2 async with aiosqlite, pydantic-settings, pytest + pytest-asyncio.

### Architecture

```
app/
  main.py, bot.py        entry point; dispatcher + error handler + command menus
  config.py              Settings from .env
  middlewares.py         one DB session per update, user upsert, language injection
  handlers/              Telegram layer only: parse input, call services, render
    start, catalog, cart, checkout, admin_orders, admin_products, admin_misc, fallback
  keyboards/             inline keyboard builders (customer, admin)
  callbacks.py, states.py  typed callback data, FSM state groups
  services/              business logic, no Telegram objects except broadcast
    cart, orders (checkout + status state machine), permissions,
    broadcast (rate limiter), stats, money, validation
  repositories/          all SQL (users, catalog, carts, orders)
  db/                    models, engine/session
  i18n/                  en.py, ru.py, t() and language detection
  formatting.py          text rendering shared by handlers
scripts/seed.py          demo catalog (idempotent)
scripts/make_test_image.py  renders docs/test-results.png from real pytest output
run.py                   one-command bootstrap
tests/                   194 tests
```

Design notes:
- **Layers.** Handlers never write SQL; services never import keyboards. The state machine (`ALLOWED_TRANSITIONS`) lives in `services/orders.py` and is enforced both when building buttons and when a button is pressed, so stale or forged callbacks cannot skip steps. Permissions are checked in the service as well as by the `IsAdmin` filter.
- **Money** is integer cents; order lines snapshot name and price at purchase time.
- **Transactions.** One session per update, committed after the handler returns, rolled back on error.
- **Broadcast** uses a spacing rate limiter (default 20/s, hard cap 30/s), retries on `retry_after`, and flags users who blocked the bot so later broadcasts skip them.
- **No migrations**: tables are created on startup. Add Alembic when the schema starts changing in production.

### How to extend

- **Online payments.** Add a `payment_method` such as `online` in `services/orders.py` (`PAYMENT_METHODS`) plus its label in both i18n files. On confirmation, create an invoice with Telegram Payments (`bot.send_invoice`, `pre_checkout_query` and `successful_payment` handlers in a new `handlers/payments.py`) or a hosted checkout link from your provider, and move the order to `confirmed` from the success callback or webhook. Orders already carry the total in cents, which is what payment APIs expect.
- **CRM / spreadsheet export.** Add `OrderService.export(since)` returning plain rows, then either a `/export` admin command that sends a CSV via `bot.send_document`, or a push call to your CRM (HubSpot, Google Sheets, a webhook) right after `OrderService.checkout` and inside `change_status`. Orders and items are already denormalised for this.
- **More languages.** Add `app/i18n/xx.py`, register it in `app/i18n/__init__.py`; the i18n tests will tell you which keys are missing.
- **Persistent FSM / scaling.** Swap `MemoryStorage` for `RedisStorage` in `bot.py`; switch the DB URL to PostgreSQL (asyncpg) for multiple instances. Use webhooks instead of polling behind a reverse proxy.

### Tests

```
pip install -r requirements-dev.txt        # or use the .venv created by run.py
python -m pytest -q
```

194 tests, about 3 seconds, no network and no real token:

- **Services**: cart math and quantity limits, order totals and price snapshots, the full status transition matrix, permission checks, broadcast rate limiter (fake clock), flood-control and blocked-user handling, stats windows and timezone, validation, money, config parsing, seed.
- **i18n**: both languages have identical keys and placeholders, every status and payment method has a label, language detection.
- **Handlers**: a real aiogram `Dispatcher` is fed raw updates while the Bot uses a recording fake session, so the tests exercise real routing, filters, middleware, FSM and SQLite. Covered: language detection and switching, the complete purchase flow, admin notification, status buttons (refused forged transition, refused non-admin, customer notified), cart controls, checkout validation, unknown input, product toggle, add/edit product FSMs, `/stats`, broadcast confirm and cancel.

`python -m scripts.make_test_image` re-runs the suite and regenerates the screenshot at the top.

### What has not been verified

- A live run against Telegram (real token, real photos, real flood-control behaviour).
- `docker build` / `docker compose up`.
- Photo cards load from the image URL on Telegram's side; a bad URL falls back to a text card (this fallback exists in code but is not covered by the tests).

### License
MIT, see [LICENSE](LICENSE).

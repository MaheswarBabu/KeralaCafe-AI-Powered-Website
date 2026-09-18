# TasteHub — Smart Restaurant Platform

A full-stack restaurant web app: browse the menu, log in, reserve a table,
order food online, track orders, chat with an AI food assistant that
recommends dishes from the **real** menu, and manage everything from an
admin dashboard - including sending customers real emails.

**Stack:** FastAPI (backend + APIs) · SQLAlchemy + MySQL/SQLite (database) ·
Jinja2 + HTML/CSS/JS (frontend) · Google Gemini (AI assistant, optional) ·
SMTP (email notifications, optional)

---

## 1. Setup

```bash
cd TasteHub
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure the database

By default the app uses a local **SQLite** file (`tastehub.db`) — zero setup,
works immediately.

To use real **MySQL** instead:

```bash
mysql -u root -p -e "CREATE DATABASE tastehub;"
export DATABASE_URL="mysql+pymysql://root:yourpassword@localhost:3306/tastehub"
```

No code changes needed — SQLAlchemy handles either database transparently.

## 3. Set a session secret (important before deploying)

Logins are stored in a signed session cookie. Set your own secret:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

If you skip this, a default dev key is used - fine for local testing, not
for production.

## 4. (Optional) Enable the real AI assistant

The AI Food Assistant works out of the box with a rule-based recommender that
already reads your real menu, filters out off-topic requests, substitutes
unavailable dishes with similar ones, and maps vague cravings ("something
sweet") to the right category. To upgrade it to genuine Gemini reasoning:

```bash
export GEMINI_API_KEY="AIzaSy..."      # free key: https://aistudio.google.com/apikey
export GEMINI_MODEL="gemini-2.5-flash"  # optional, this is the default
```

## 5. (Optional) Enable real emails

Order confirmations, cancellations, and "item change requested" notices are
emailed to customers. Without SMTP configured, emails just print to the
server console (a "dry run") so you can develop without real credentials:

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your_email@gmail.com"
export SMTP_PASSWORD="your_app_password"   # a Gmail "App Password", not your login password
export FROM_EMAIL="your_email@gmail.com"
```

## 6. Seed the database

```bash
python seed.py
```

Creates the tables, 12 sample dishes, 10 restaurant tables, and a **default
admin account**:

```
Email:    admin@tastehub.local
Phone:    9999999999
Password: admin123
```

Change these before deploying by setting `ADMIN_EMAIL` / `ADMIN_PHONE` /
`ADMIN_PASSWORD` env vars *before* running `seed.py` for the first time.
Safe to re-run — it skips seeding anything that already exists.

## 7. Run it

```bash
uvicorn app:app --reload
```

Open **http://127.0.0.1:8000**

---

## Login system

- **Customers** sign up with name, email, phone, and password at `/register`,
  then log in at `/login`. Logging in is required before placing an order or
  a table reservation (so we always know who to email).
- **Admin** logs in with the same `/login` form using the admin account's
  email/phone + password. The nav bar shows an extra **Admin** link only for
  admin accounts.
- Sessions are signed cookies (via Starlette's `SessionMiddleware`) - no JWT
  or extra token handling needed on the frontend.
- Passwords are hashed with PBKDF2-HMAC-SHA256 + a random per-user salt
  (see `auth.py`) - never stored in plain text.

## Admin dashboard

Once logged in as admin, `/admin/orders`, `/admin/reservations`, and
`/admin/menu` become available (also linked from the nav bar):

- **Orders tab** — view every online order, update its status through the
  pipeline (Order Placed → Confirmed → Preparing → Out for Delivery →
  Delivered), **cancel** an order with a reason, or **request an item
  change** with a custom message (e.g. "Chicken 65 is sold out, would you
  like Chilli Paneer instead?"). Both actions email the customer.
- **Reservations tab** — view every table booking, cancel it with a reason,
  or send a change request - both emailed to the customer.
- **Menu tab** — add, edit, or delete dishes, including uploading a real
  image file (saved to `static/images/uploads/`) or just pasting an image
  URL. Toggle vegetarian/availability with checkboxes.

## Email notifications

`email_service.py` sends (or, without SMTP configured, prints to the
console) an email for:

| Event | Trigger |
|---|---|
| Order confirmed | Customer places an order |
| Order cancelled | Admin cancels an order (reason included) |
| Order item-change requested | Admin requests a change (message included) |
| Reservation confirmed | Customer books a table |
| Reservation cancelled | Admin cancels a reservation (reason included) |

## Project structure

```
TasteHub/
├── app.py               FastAPI app: pages, auth, admin routes, all JSON APIs
├── auth.py              Password hashing (PBKDF2) + session/login dependencies
├── email_service.py     SMTP email sending (console dry-run if unconfigured)
├── database.py          SQLAlchemy engine/session (SQLite default, MySQL via env var)
├── models.py             ORM models: users, foods, tables, reservations, orders, order_items
├── schemas.py            Pydantic request/response schemas
├── ai_service.py         AI Food Assistant (Gemini if key set, else rule-based)
├── seed.py               Sample data + default admin account loader
├── requirements.txt
├── .env.example
├── templates/            Jinja2 pages: home, menu, login, register, reservation,
│                         cart, checkout, orders, ai_assistant, admin_orders,
│                         admin_reservations, admin_menu
└── static/
    ├── style.css         Design system (colors, type, components)
    ├── script.js         Cart state, toast notifications, nav toggle
    └── images/uploads/   Admin-uploaded dish photos land here
```

## API reference

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Create a customer account, logs them in |
| POST | `/api/auth/login` | Log in with email/phone + password |
| POST | `/api/auth/logout` | Clear the session |
| GET | `/api/foods` | List menu items (filter by `category`, `is_veg`, `max_price`, `search`) |
| GET | `/api/foods/{id}` | Single dish |
| GET | `/api/tables/availability?date=&time=&guests=` | Check for a free table |
| POST | `/api/reservations` | Create a reservation (**login required**) |
| GET | `/api/reservations/{id}` | Look up a reservation |
| POST | `/api/orders` | Place an order (**login required**) |
| GET | `/api/orders/{id}` | Order status + items |
| GET | `/api/orders/phone/{phone}` | All orders for a phone number |
| POST | `/api/ai/recommend` | AI assistant recommendation (`{"message": "..."}`) |

Admin actions (`/admin/orders/{id}/status`, `/cancel`, `/request-change`,
`/admin/reservations/{id}/cancel`, `/request-change`, `/admin/menu/add`,
`/{id}/edit`, `/{id}/delete`) are HTML form posts protected by an admin-only
session check, used directly by the admin dashboard pages.

Interactive API docs are auto-generated by FastAPI at **`/docs`**.

## Notes

- The menu page (`/menu`) doubles as the ordering page — add items there and
  a live cart sidebar with a "Proceed to Checkout" button appears alongside
  it (no separate "Order Online" tab). Once an item is in the cart its
  button turns into a "- qty +" stepper right on the menu card.
- Table reservations can be **browsed and checked for availability without
  logging in** — you're only asked to log in at the final "confirm" step,
  same as checkout.
- Logged-in customers see their orders automatically on `/orders` — no
  phone number or order ID needed. Guests (or anyone checking someone else's
  order) can still look one up manually.
- No real payment gateway is wired up — checkout supports Cash on Delivery
  and a simulated UPI option.
- The cart lives in the browser's `localStorage`, so it survives page
  reloads/navigation but is per-device.
- Order codes are displayed as `TH1000+order_id` (e.g. order #1 → `TH1001`).
- `ai_service.py` never lets the model invent a dish: it only recommends
  `food_id`s that exist in your live `foods` table.
- The assistant is prompted (and the fallback is coded) to: **decline
  off-topic requests** ("order me a phone"), **substitute unavailable dishes**
  with similar real ones ("veg biryani" → suggests Veg Fried Rice etc. when
  we don't have veg biryani), and **map vague cravings** ("something sweet")
  to the right menu category.

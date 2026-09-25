# 🕵️ UserScope

**Username & phone intelligence dashboard** — enter one username and find every social profile carrying it across 462+ platforms, or analyze any phone number offline — all live in your browser.

100% free. No APIs, no paid services, no external web frameworks. Pure Python + vanilla HTML/CSS/JS.

> UserScope is a fully rebranded, rebuilt version of the classic username-hunting engine — wrapped in a professional local dashboard with live progress, filtering and exports.

---

## ✨ Features

- **One input, hundreds of checks** — scans 462+ social networks for a username in one go.
- **Live results** — each site's answer streams into a table *while* the scan runs (no waiting for the end).
- **Status intelligence** per site:
  - 🟢 **Claimed** — profile exists
  - ⚪ **Available** — username is free
  - 🟡 **Error** — could not verify
  - 🔴 **Blocked** — site's bot detection refused us (proxy may help)
  - 🟣 **Illegal** — the site doesn't allow that username format
- **Filters & tabs** — All / Claimed / Available / Problems.
- **Live activity feed** with response times.
- **Clean exports** — JSON, CSV or TXT download after a scan.
- **NSFW filter** toggle to include or skip adult sites.
- **Localhost-only dashboard** — bound to `127.0.0.1`, never exposed online.
- **Timeouts** configurable per request (15 / 30 / 60 s).

### 📱 Phone lookup (built-in)

A second mode inside the same dashboard — switch with the **Username search / Phone lookup** tabs (or open `#phone` directly). 100% free: no keys, no accounts, no paid lookups.

**What you get per number:**

| Field | Example |
|---|---|
| Valid / Possible | ✅ valid, ✅ possible |
| Country + region | Pakistan (PK) |
| Country code | +92 |
| National number | 3001234567 |
| Line type | mobile / fixed line / voip / toll free… |
| Carrier | Jazz, Ufone, Airtel, Jio… (where offline data exists) |
| Timezone | Asia/Karachi |
| Local time | 2026-09-25 14:30 PKT |
| Geographic hint | region/area name (offline library) |
| Formats | E.164 `+923001234567` · international · national · tel: |

- **Accepts any format** — `+92 300 1234567`, `03001234567`, `00923001234567`. Numbers without a `+` prefix are auto-detected as Pakistan.
- **Junk input is safe** — invalid numbers are reported gracefully, never crash.
- **Optional web visibility scan** (checkbox, off by default): a free **DuckDuckGo** HTML search of the number — no API key, no account. Shows public pages that mention the number; if search is blocked/rate-limited it says so and returns nothing.
- **History** — last 50 lookups saved to `results/phone_history.json`. Click any row to re-analyze, or **Clear** the list.
- **Exports** — copy the number, or download a per-number **JSON / CSV** report.

**Very important:** this is offline/public data only — validation, formats, carrier, timezone, and (optionally) public pages. It does **not** reveal anyone's name, photo, or location. For demo/testing, use your own number.

---

## 🚀 Quick start

```bat
:: 1. install dependencies once
pip install -r requirements.txt

:: 2. run the dashboard (or double-click start.bat)
python app\server.py
```

Open **http://127.0.0.1:4545/ui/** → type a username → **Search**.

```
  UserScope dashboard running at:
  ->  http://127.0.0.1:4545/ui/
  Press Ctrl+C to stop.
```

---

## 🧪 Tests

```bat
python -m pytest -q        :: 34 tests, fully offline
```

Test suite covers the site registry, the live runner state machine, cancellation, exports, the phone analyzer + history API, and the whole HTTP API end-to-end (with the network engine faked so tests run anywhere).

---

## 🗂️ Project structure

```
UserScope/
├─ userscope/              # engine package (rebranded, trimmed)
│  ├─ engine.py            # core search engine (multi-threaded requests)
│  ├─ sites.py             # site registry loader (+ NSFW filter)
│  ├─ notify.py            # output notification interface
│  ├─ result.py            # status enums + result model
│  └─ resources/data.json  # 462+ site definitions (bundled, offline)
├─ app/
│  ├─ runner.py            # engine wrapper -> live state, queue, exports
│  ├─ phone.py             # phone analyzer + optional DDG search + history
│  ├─ server.py            # stdlib dashboard server + JSON API
│  └─ ui/                  # dashboard UI (index.html, style.css, app.js, favicon.svg)
├─ tests/                  # offline test-suite (test_phone.py, test_api.py, …)
├─ vercel.json             # static-only: makes Vercel imports build (UI served, backend local-only)
├─ start.bat               # one-click launcher (Windows)
├─ requirements.txt        # includes phonenumbers (offline, Apache-2.0)
├─ pyproject.toml
└─ LICENSE                 # MIT
```

---

## 🔌 How it works

```
   browser ──► app/server.py   (127.0.0.1:4545, localhost only)
                   │
                   ├─ /api/search          -> starts username scan (background thread)
                   ├─ /api/status          -> polled by the UI every ~1.2s (live rows)
                   ├─ /api/export          -> JSON / CSV / TXT username report
                   ├─ /api/phone?num=&web= -> analyze a number (offline) + optional DDG search
                   ├─ /api/phone/history   -> saved lookups (results/phone_history.json)
                   └─ /api/phone/history/clear (POST) -> wipe history

   runner.py ──► userscope/engine.py.search(username, sites, notifier)
                           │
        concurrent requests to 462+ sites, zero external APIs

   phone.py ──► phonenumbers (offline validation/formats/carrier/timezone)
                   └─ optional: DuckDuckGo HTML search (free, no key)
```

The engine fires parallel HTTP probes, our custom notifier forwards every result into a thread-safe live state that the UI re-renders continuously.

---

## ⚠️ Notes

- **This is a local-first desktop tool.** The dashboard binds to `127.0.0.1`; the scan engine runs in background threads and writes history to local files — that is exactly why it will not work as a hosted/serverless web app. Keep it on your own machine.
- `vercel.json` + `public/` exist only so a Vercel import **builds and shows the UI** (static files served at the site root). The search **will not run** there — there is no backend. `public/` is just a static mirror of `app/ui/` for deployment; when you change the UI locally, mirror the files there before redeploying.
- Results depend on the network you're on. Sites behind strict bot-detection (WAF) show **Blocked** — a home/mobile IP works far better than a datacenter/VPN one.
- One full scan can take **minutes** (462 sites × network round-trips). That's normal — watch it live.
- **Use responsibly.** Search your own usernames/numbers or run authorized OSINT work only. Many sites prohibit automated probing; keep within the law and site terms.

---

## 📄 License

MIT — see [LICENSE](LICENSE). Engine core adapted from the MIT-licensed open source Sherlock project.
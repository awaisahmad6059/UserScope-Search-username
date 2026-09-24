# 🕵️ UserScope

**Username intelligence dashboard** — enter one username, find every social profile carrying it, live in your browser.

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
python -m pytest -q        :: 20 tests, fully offline
```

Test suite covers the site registry, the live runner state machine, cancellation, exports and the whole HTTP API end-to-end (with the network engine faked so tests run anywhere).

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
│  ├─ server.py            # stdlib dashboard server + JSON API
│  └─ ui/                  # dashboard UI (index.html, style.css, app.js)
├─ tests/                  # offline test-suite
├─ start.bat               # one-click launcher (Windows)
├─ requirements.txt
├─ pyproject.toml
└─ LICENSE                 # MIT
```

---

## 🔌 How it works

```
   browser ──► app/server.py   (127.0.0.1:4545, localhost only)
                   │
                   ├─ /api/search   -> starts scan on a background thread
                   ├─ /api/status   -> polled by the UI every ~1.2s (live rows)
                   └─ /api/export   -> JSON / CSV / TXT downloads

   runner.py ──► userscope/engine.py.search(username, sites, notifier)
                           │
        concurrent requests to 462+ sites, zero external APIs
```

The engine fires parallel HTTP probes, our custom notifier forwards every result into a thread-safe live state that the UI re-renders continuously.

---

## ⚠️ Notes

- Results depend on the network you're on. Sites behind strict bot-detection (WAF) show **Blocked** — a home/mobile IP works far better than a datacenter/VPN one.
- One full scan can take **minutes** (462 sites × network round-trips). That's normal — watch it live.
- **Use responsibly.** Search your own usernames or run authorized OSINT work only. Many sites prohibit automated probing; keep within the law and site terms.

---

## 📄 License

MIT — see [LICENSE](LICENSE). Engine core adapted from the MIT-licensed open source Sherlock project.
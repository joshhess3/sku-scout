# BestBuy Restock Watcher

Monitors Best Buy SKUs within a chosen radius of a ZIP code and sends Telegram alerts when stores report **in-stock** availability. Includes backoff handling, optional HTML fallback sniff, hourly uptime heartbeats, and a simple Windows batch manager.

## Features
- Monitors multiple SKUs via Best Buy API
- Distance filter + priority stores
- Telegram alerts with product name, SKU, stores, and link
- Hourly uptime heartbeat (configurable)
- State file so you’re not spammed on every poll
- Minimal Windows manager to start/stop/check logs

## Quick start
1. Install Python 3.9+.
2. Clone the repo and open a terminal in the repo folder.
3. Create a virtual env:
   ```bat
   python -m venv venv
   venv\Scripts\pip install -U pip
   venv\Scripts\pip install requests python-dotenv tzdata

Copy .env.example to .env and fill in your own keys.

Run python bestbuy_restock_watcher_telegram_22s.py or use the watcher_manager.bat.

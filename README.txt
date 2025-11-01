🛰️ SKU-Scout (BestBuy Stock Watcher)

SKU-Scout is a lightweight Python tool that monitors Best Buy product SKUs by ZIP code and radius, then sends instant Telegram alerts when nearby stores have in-stock availability.
Perfect for tracking restocks, product drops, and local inventory — all with simple setup and real-time notifications.

───────────────────────────────
FEATURES
───────────────────────────────
• Track multiple SKUs using the official Best Buy API
• Filter by ZIP code and distance (e.g., 30 miles around 33545)
• Telegram alerts with product name, SKU, store list, and direct Best Buy link
• Hourly uptime “heartbeat” notifications (configurable)
• Avoid duplicate alerts with local state caching
• Simple Windows batch manager to start/stop/status/log watcher

───────────────────────────────
FOLDER STRUCTURE
───────────────────────────────
C:\bestbuy-watcher
│
├── bestbuy_restock_watcher_telegram_60s.py
├── watcher_manager.bat
├── requirements.txt
├── .env.example
├── README_SETUP.txt
│
├── availability_state.json (auto-created)
├── restock.log (auto-created)
├── watcher.pid (auto-created)
│
└── venv\ (auto-created, do not upload)

───────────────────────────────
FULL SETUP GUIDE
───────────────────────────────

Create the Folder
Make a folder at:
C:\bestbuy-watcher

Add Project Files
Place these files inside:
bestbuy_restock_watcher_telegram_60s.py
watcher_manager.bat
requirements.txt
.env.example
README_SETUP.txt

Open Command Prompt
Press Win + R, type “cmd”, and press Enter.
Navigate to the folder:
cd C:\bestbuy-watcher

Create a Virtual Environment
python -m venv venv

Activate the Virtual Environment
venv\Scripts\activate

Upgrade pip
python -m pip install -U pip

Install Dependencies
pip install -r requirements.txt

Copy and Configure the Environment File
copy .env.example .env

Then open .env in Notepad and fill in:
BESTBUY_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ZIP_CODE, etc.

Example:
BESTBUY_API_KEY=your_bestbuy_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
ZIP_CODE=12345
MAX_DISTANCE_MI=30
SKU_LIST=1234567,7654321
PRIORITY_STORE_IDS=1000,450,665
HEARTBEAT_ENABLED=true

Run the Watcher
python bestbuy_restock_watcher_telegram_60s.py

(Optional) Use the Batch Manager
watcher_manager.bat

This lets you:
– Start or stop the watcher
– View logs
– Check status
– Edit the .env file quickly

───────────────────────────────
CONFIGURATION HIGHLIGHTS
───────────────────────────────
BESTBUY_API_KEY .......... Your Best Buy API key
TELEGRAM_BOT_TOKEN ....... Your Telegram bot token
TELEGRAM_CHAT_ID ......... Your Telegram user or group ID
ZIP_CODE ................. ZIP code for search
MAX_DISTANCE_MI .......... Search radius (miles)
SKU_LIST ................. Comma-separated SKUs
POLL_EVERY_SECONDS ....... Polling interval (seconds)
HEARTBEAT_ENABLED ........ Enables hourly uptime message

───────────────────────────────
TIPS
───────────────────────────────
• Adjust ZIP and radius for your area.
• Use PRIORITY_STORE_IDS to check preferred stores first.
• restock.log and availability_state.json are created automatically.
• If you hit API limits, increase POLL_EVERY_SECONDS to 120 or higher.
• watcher_manager.bat automates start/stop and handles venv activation.

───────────────────────────────
LICENSE
───────────────────────────────
MIT License — free to use, modify, and share.
Pull requests and community contributions are welcome.

───────────────────────────────
DISCLAIMER
───────────────────────────────
This project is unofficial and not affiliated with Best Buy.
Use responsibly and in compliance with:

Best Buy API Documentation: https://developer.bestbuy.com/documentation

Best Buy API Terms of Service: https://developer.bestbuy.com/terms

───────────────────────────────
CREDITS
───────────────────────────────
Developed and maintained for the community by enthusiasts of open data and local inventory tracking.
Special thanks to contributors improving Best Buy API tooling.
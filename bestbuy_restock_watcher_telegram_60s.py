#!/usr/bin/env python3
import os, re, time, json, logging, atexit, random
from typing import Dict, List, Tuple, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- .env ---
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
except Exception:
    pass

# ===== ENV =====
BESTBUY_API_KEY    = os.getenv("BESTBUY_API_KEY", "").strip()
# Public-safe defaults (no real ZIP/locations baked in):
ZIP_CODE           = os.getenv("ZIP_CODE", "00000").strip()
MAX_DISTANCE_MI    = float(os.getenv("MAX_DISTANCE_MI", "30") or "30")
POLL_EVERY_SECONDS = int(os.getenv("POLL_EVERY_SECONDS", "60") or "60")
PER_REQUEST_DELAY_S= float(os.getenv("PER_REQUEST_DELAY_S", "1.5") or "1.5")
RATE_BACKOFF_S     = float(os.getenv("RATE_BACKOFF_S", "3.0") or "3.0")

# State / alert behavior
ALERT_ON_FIRST_SEEN  = os.getenv("ALERT_ON_FIRST_SEEN", "true").lower() in ("1","true","yes","y")
FORCE_ALERT_ON_MATCH = os.getenv("FORCE_ALERT_ON_MATCH", "false").lower() in ("1","true","yes","y")

# Heartbeat (hourly uptime ping)
HEARTBEAT_ENABLED        = os.getenv("HEARTBEAT_ENABLED", "true").lower() in ("1","true","yes","y")
HEARTBEAT_EVERY_MINUTES  = int(os.getenv("HEARTBEAT_EVERY_MINUTES", "60") or "60")

_raw_skus_env = os.getenv("SKU_LIST", "")
_clean_before_hash = _raw_skus_env.split("#", 1)[0]
_clean_env = re.sub(r"[^0-9,\s]", "", _clean_before_hash)
SKU_LIST = [s.strip() for s in _clean_env.split(",") if s.strip().isdigit()]

PRIORITY_STORE_IDS: List[int] = []
prio_env = os.getenv("PRIORITY_STORE_IDS", "")
if prio_env.strip():
    for token in re.split(r"[,\s]+", prio_env.strip()):
        if token.isdigit():
            PRIORITY_STORE_IDS.append(int(token))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_STARTUP_PING = os.getenv("TELEGRAM_STARTUP_PING", "true").lower() in ("1","true","yes","y")
# Public repos should default to quieter logs:
TELEGRAM_VERBOSE      = os.getenv("TELEGRAM_VERBOSE", "false").lower() in ("1","true","yes","y")

HTML_FALLBACK = os.getenv("HTML_FALLBACK", "true").lower() in ("1","true","yes","y")
# Generic default label (no real store name baked in)
FALLBACK_STORE_HINT = os.getenv("FALLBACK_STORE_HINT", "Your City").strip()
FALLBACK_MIN_HIT = os.getenv("FALLBACK_MIN_HIT",
    "pickup today|ready today|available today|in stock|ready for pickup").strip()
FALLBACK_RE = re.compile(FALLBACK_MIN_HIT, re.I)  # ignore case

# Public repos should default to NOT logging URLs/JSON unless opted in:
DEBUG_LOG_URLS  = os.getenv("DEBUG_LOG_URLS", "false").lower() in ("1","true","yes","y")
DEBUG_LOG_JSON  = os.getenv("DEBUG_LOG_JSON", "false").lower() in ("1","true","yes","y")

STATE_PATH = os.path.join(SCRIPT_DIR, os.getenv("STATE_PATH", "./availability_state.json"))
LOG_PATH   = os.path.join(SCRIPT_DIR, os.getenv("LOG_PATH", "./restock.log"))
PID_PATH   = os.path.join(SCRIPT_DIR, os.getenv("WATCHER_PID_PATH", "./watcher.pid"))

# --- logging ---
os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
)
logging.info("======== Best Buy Watcher starting ========")
logging.info(f"ZIP/Rad: {ZIP_CODE}/{int(MAX_DISTANCE_MI)}mi  Poll: {POLL_EVERY_SECONDS}s  Delay: {PER_REQUEST_DELAY_S}s")
# Avoid echoing raw SKUs in public logs by default
logging.info(f"SKUs configured: {len(SKU_LIST)}")
logging.info(f"Priority stores: {PRIORITY_STORE_IDS or 'None (prefers nearest)'}")
logging.info(f"Paths: state={STATE_PATH} log={LOG_PATH} pid={PID_PATH}")
logging.info(f"Alert policy: ALERT_ON_FIRST_SEEN={ALERT_ON_FIRST_SEEN} FORCE_ALERT_ON_MATCH={FORCE_ALERT_ON_MATCH}")
logging.info(f"Heartbeat: enabled={HEARTBEAT_ENABLED} every={HEARTBEAT_EVERY_MINUTES}m")

# --- PID file ---
def write_pid():
    try:
        with open(PID_PATH, "w", encoding="ascii") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logging.error(f"Failed to write PID file: {e}")

def cleanup_pid():
    try:
        if os.path.exists(PID_PATH):
            os.remove(PID_PATH)
    except Exception:
        pass

write_pid()
atexit.register(cleanup_pid)

# --- sanity ---
if not BESTBUY_API_KEY:
    logging.error("BESTBUY_API_KEY is missing in .env"); raise SystemExit(1)

# --- HTTP session ---
import requests
session = requests.Session()
session.headers.update({"User-Agent": "bb-restock-watcher/2.0"})

BASE = "https://api.bestbuy.com/v1"
_rate_limit_until = 0.0  # epoch seconds; skip API calls while > time.time()

# --- Telegram ---
def tg_send_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = session.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
        if TELEGRAM_VERBOSE: logging.info(f"[telegram] status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        logging.error(f"Telegram error: {e}")

# --- Minimal Markdown escaping (keeps titles clean) ---
_MD_RE = re.compile(r"([_*`\[\]\(\)])")
def escape_md(s: str) -> str:
    if not s: return ""
    return _MD_RE.sub(r"\\\1", s)

# ---------- Product metadata (name/url) cache ----------
_product_cache: Dict[str, Dict] = {}

def fetch_product_meta(sku: str) -> Dict:
    """Get product name+url (cached). Includes one gentle retry on 403/5xx."""
    if sku in _product_cache:
        return _product_cache[sku]
    if time.time() < _rate_limit_until:
        return {"sku": sku, "name": None, "url": None, "image": None}

    def _call():
        url = f"{BASE}/products(sku={sku})"
        params = {
            "apiKey": BESTBUY_API_KEY,
            "format": "json",
            "show": "sku,name,url,image,shortDescription,salePrice,regularPrice",
        }
        if DEBUG_LOG_URLS: logging.info(f"[meta] {url}?apiKey=***")
        return session.get(url, params=params, timeout=20)

    r = _call()
    if r.status_code in (403, 429, 500, 502, 503, 504):
        time.sleep(RATE_BACKOFF_S)
        r = _call()

    if r.status_code == 403:
        logging.warning(f"[{sku}] meta 403; using fallback url/name")
        _product_cache[sku] = {"sku": sku, "name": None, "url": None, "image": None}
        return _product_cache[sku]

    try:
        r.raise_for_status()
    except Exception as e:
        logging.warning(f"[{sku}] meta HTTP error: {e}")
        _product_cache[sku] = {"sku": sku, "name": None, "url": None, "image": None}
        return _product_cache[sku]

    js = r.json()
    items = js.get("products", [])
    name = None
    prod_url = None
    img = None
    if items:
        it = items[0]
        name = it.get("name")
        prod_url = it.get("url")
        img = it.get("image")
    _product_cache[sku] = {"sku": sku, "name": name, "url": prod_url, "image": img}
    return _product_cache[sku]

# ---------- Real-time availability ----------
def real_time_availability_postal(sku: str, postal: str) -> Tuple[bool, List[Dict], bool]:
    """Use official products/{sku}/stores.json with postalCode."""
    global _rate_limit_until
    if time.time() < _rate_limit_until:
        return (False, [], True)

    url = f"{BASE}/products/{sku}/stores.json"
    params = {"apiKey": BESTBUY_API_KEY, "postalCode": postal, "pageSize": "250"}
    if DEBUG_LOG_URLS: logging.info(f"[rt] {url}?postalCode={postal}&apiKey=***")
    r = session.get(url, params=params, timeout=20)

    if r.status_code == 403:
        _rate_limit_until = time.time() + RATE_BACKOFF_S * 2
        logging.warning(f"[{sku}] 403 Over Quota — pausing until {_rate_limit_until:.0f}")
        return (False, [], True)

    r.raise_for_status()
    js = r.json()
    stores = js.get("stores", [])
    if DEBUG_LOG_JSON: logging.info(f"[rt {sku}] JSON stores count: {len(stores)}")

    # Prefer name/url from RT if present; else from product meta; else generic
    rt_name = js.get("name")
    rt_url  = js.get("url")
    meta = fetch_product_meta(sku)
    name = rt_name or meta.get("name") or f"SKU {sku}"
    url_fallback = rt_url or meta.get("url") or f"https://www.bestbuy.com/site/{sku}.p"

    payloads = []
    for st in stores:
        sid = st.get("storeID") or st.get("storeId") or st.get("id")
        dist = st.get("distance")
        if dist is not None:
            try:
                if float(dist) > float(MAX_DISTANCE_MI):
                    continue
            except Exception:
                pass
        payloads.append({
            "store": {"storeId": int(sid) if sid is not None else None,
                      "name": st.get("name") or st.get("longName"),
                      "city": st.get("city"), "region": st.get("state") or st.get("region"),
                      "postalCode": st.get("postalCode"), "distance": dist},
            "product": {"sku": sku, "name": name, "url": url_fallback, "image": meta.get("image"),
                        "inStoreAvailability": True}
        })

    # Prefer priority stores first, but don't drop others
    if PRIORITY_STORE_IDS and payloads:
        rank = {sid: i for i, sid in enumerate(PRIORITY_STORE_IDS)}
        payloads.sort(key=lambda p: (
            0 if (p["store"].get("storeId") in rank) else 1,
            rank.get(p["store"].get("storeId"), 10**6),
            float(p["store"].get("distance") or 10**6)
        ))
    else:
        payloads.sort(key=lambda p: float(p["store"].get("distance") or 10**6))

    return (len(payloads) > 0, payloads, False)

# ---------- HTML fallback ----------
def html_fallback_pickup(sku: str) -> Tuple[bool, Optional[Dict]]:
    if not HTML_FALLBACK or time.time() < _rate_limit_until:
        return (False, None)
    try:
        url = f"https://www.bestbuy.com/site/{sku}.p"
        if DEBUG_LOG_URLS: logging.info(f"[fallback] GET {url}")
        r = session.get(url, timeout=20)
        if r.status_code >= 400: return (False, None)
        text = r.text.lower()
        if FALLBACK_STORE_HINT.lower() in text and FALLBACK_RE.search(text):
            meta = fetch_product_meta(sku)
            return (True, {"store":{"storeId":None,"name":FALLBACK_STORE_HINT,"city":FALLBACK_STORE_HINT,
                                    "region":"","postalCode":ZIP_CODE,"distance":None},
                           "product":{"sku":sku,"name":meta.get('name') or f'SKU {sku}',
                                      "url":meta.get('url') or url,"image":meta.get('image'),
                                      "inStoreAvailability":True}})
        return (False, None)
    except Exception as e:
        logging.error(f"[fallback] error: {e}")
        return (False, None)

# ---------- State & formatting ----------
def load_state() -> dict:
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load state: {e}")
    return {}

def save_state(state: dict) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save state: {e}")

def escape_md_text(s: str) -> str:
    return escape_md(s)

def format_alert(payloads: List[Dict]) -> str:
    p0 = payloads[0]["product"]
    lines = []
    lines.append("🔥 *In-Stock Alert!* 🔥")
    lines.append(f"🛒 *{escape_md_text(p0.get('name') or 'Unknown Product')}*")
    lines.append(f"🔢 *SKU:* `{p0.get('sku')}`")
    for pay in payloads:
        st = pay["store"]
        if st.get("storeId"):
            lines.append(
                f"📍 Store {st['storeId']} — {escape_md_text(st.get('name') or '')} "
                f"({escape_md_text(st.get('city') or '')}, {escape_md_text(st.get('region') or '')}) • "
                f"{escape_md_text(str(st.get('postalCode','')))}, {escape_md_text(str(st.get('distance','?')))} mi"
            )
        else:
            lines.append(f"📍 {escape_md_text(FALLBACK_STORE_HINT)} (HTML fallback)")
    url = p0.get("url") or f"https://www.bestbuy.com/site/{p0.get('sku')}.p"
    if not url.startswith("http"): url = "https://" + url.lstrip("/")
    lines.append(f"🔗 [View on Best Buy]({url})")
    return "\n".join(lines)

def should_alert(prev: dict, sku: str, now_in: bool) -> Tuple[bool, str]:
    if FORCE_ALERT_ON_MATCH and now_in:
        return True, "FORCE_ALERT_ON_MATCH"
    prev_had = prev.get(f"{sku}__had_stock")
    if prev_had is None:
        return (ALERT_ON_FIRST_SEEN and now_in, f"first_seen now_in={now_in}")
    return ((prev_had is False) and now_in, f"flip prev_had={prev_had} -> now_in={now_in}")

# ---------- Heartbeat helpers ----------
def _format_duration(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d: parts.append(f"{d}d")
    if h or d: parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)

# ---------- Poll loop ----------
def poll_once(state: dict, product_cache: dict) -> Tuple[dict, int]:
    """Returns (state, alerts_sent_this_loop)"""
    if not isinstance(state, dict): state = {}
    loop_jitter = random.uniform(0, 0.3)
    alerts_sent = 0

    for raw_sku in SKU_LIST:
        sku = raw_sku.strip()
        if not sku.isdigit():
            logging.error(f"[{sku}] invalid SKU; must be numeric.")
            time.sleep(PER_REQUEST_DELAY_S); continue

        in_stock_payloads: List[Dict] = []

        rt_has, rt_payloads, rate_limited = real_time_availability_postal(sku, ZIP_CODE)
        if rate_limited:
            logging.info(f"[{sku}] rate-limited; skipping fallbacks this loop.")
        if rt_has:
            in_stock_payloads.extend(rt_payloads)
            logging.info(f"[{sku}] RT hits: {len(rt_payloads)}")

        if not in_stock_payloads and not rate_limited:
            fb_has, fb_payload = html_fallback_pickup(sku)
            if fb_has and fb_payload: in_stock_payloads.append(fb_payload)

        now_in = len(in_stock_payloads) > 0
        logging.info(f"[{sku}] now_in={now_in} hits={len(in_stock_payloads)}")

        dec, why = should_alert(state, sku, now_in)
        logging.info(f"[{sku}] alert_decision={dec} reason={why}")

        if dec:
            msg = format_alert(in_stock_payloads) if now_in else f"ℹ️ {sku} still out of stock."
            tg_send_message(msg)
            alerts_sent += 1

        state[f"{sku}__had_stock"] = bool(now_in)
        state[f"{sku}__stores"] = [p["store"].get("storeId") for p in in_stock_payloads if p["store"].get("storeId")]
        save_state(state)

        time.sleep(PER_REQUEST_DELAY_S + loop_jitter)

    return state, alerts_sent

def main():
    start_ts = time.time()
    next_heartbeat = start_ts + HEARTBEAT_EVERY_MINUTES * 60 if HEARTBEAT_ENABLED else float("inf")
    total_alerts = 0
    total_loops = 0

    if TELEGRAM_STARTUP_PING:
        tg_send_message("✅ Best Buy watcher started. I'll notify you on in-stock finds.")

    state = load_state(); product_cache = {}
    logging.info(f"Starting Best Buy Telegram Watcher ({POLL_EVERY_SECONDS}s loop)...")
    while True:
        try:
            state, sent = poll_once(state, product_cache)
            total_alerts += sent
            total_loops += 1
        except requests.HTTPError as e:
            logging.error(f"HTTP error: {e}"); time.sleep(RATE_BACKOFF_S)
        except Exception as e:
            logging.error(f"Unhandled error in poll loop: {e}"); time.sleep(RATE_BACKOFF_S)

        # Heartbeat: every HEARTBEAT_EVERY_MINUTES, report uptime and counters
        now = time.time()
        if now >= next_heartbeat:
            uptime = _format_duration(now - start_ts)
            tg_send_message(f"🟢 Watcher heartbeat — up {uptime}\n"
                            f"• Loops: {total_loops}\n"
                            f"• Alerts sent: {total_alerts}\n"
                            f"• SKUs: {', '.join(SKU_LIST) or '—'}")
            while next_heartbeat <= now:
                next_heartbeat += HEARTBEAT_EVERY_MINUTES * 60

        time.sleep(POLL_EVERY_SECONDS)

if __name__ == "__main__":
    main()

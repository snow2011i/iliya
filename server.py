# ==============================================================================
#  Iliya Gateway  —  server.py
#  دروازه‌ی تونل VLESS روی WebSocket + داشبورد مدیریتی + API فروش (برای ربات)
#  پیاده‌سازی کاملاً اورجینال — مخصوص Iliya
# ==============================================================================
import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets
import socket
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import aiofiles
import httpx
import uvicorn
from fastapi import (Depends, FastAPI, Header, HTTPException, Request, WebSocket,
                     WebSocketDisconnect)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response

from ui import dashboard_html, login_html, sub_page_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("Iliya")

# ── تنظیمات پایه ────────────────────────────────────────────────────────
BRAND = "Iliya"
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
STATE_FILE = DATA_DIR / "iliya_state.json"
SECRET_FILE = DATA_DIR / "iliya_secret.key"
PORT = int(os.environ.get("PORT", 8000))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "iliya")
# کلید مشترک بین سرور و ربات تلگرام (برای ساخت کانفیگ از سمت ربات)
BOT_API_KEY = os.environ.get("BOT_API_KEY", "iliya-secret-bridge")
DEFAULT_HOST = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost")


def _load_secret() -> str:
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if SECRET_FILE.exists():
            v = SECRET_FILE.read_text(encoding="utf-8").strip()
            if v:
                return v
        v = secrets.token_urlsafe(32)
        SECRET_FILE.write_text(v, encoding="utf-8")
        return v
    except Exception as e:
        log.warning(f"secret persist failed: {e}")
        return secrets.token_urlsafe(32)


SECRET = _load_secret()
CONFIG = {"host": DEFAULT_HOST}

# ── حالت در‌حافظه ───────────────────────────────────────────────
CONFIGS: dict = {}          # uuid -> config dict
AUTH = {"password_hash": None}
SESSIONS: dict = {}
CONNS: dict = {}            # conn_id -> {uuid, ip, bytes, ...}
STATS = {"total_bytes": 0, "total_requests": 0, "total_errors": 0, "start": time.time()}
HOURLY = defaultdict(int)
ACTIVITY = deque(maxlen=200)
LOCK = asyncio.Lock()
SAVE_LOCK = asyncio.Lock()
_buckets: dict = {}         # uuid -> token bucket (محدودیت سرعت)

app = FastAPI(title="Iliya Gateway", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


# ── کمکی‌ها ──────────────────────────────────────────────────
def hash_pw(pw: str) -> str:
    return hashlib.sha256(f"{pw}:{SECRET}".encode()).hexdigest()


def new_uuid() -> str:
    h = secrets.token_hex(16)
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def now() -> datetime:
    return datetime.now()


def fmt_bytes(b: int) -> str:
    b = float(b)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or unit == "TB":
            return f"{b:.2f} {unit}" if unit != "B" else f"{int(b)} B"
        b /= 1024


def log_act(kind: str, msg: str, level: str = "info"):
    ACTIVITY.append({"kind": kind, "level": level, "msg": msg, "time": now().isoformat()})


def get_host(request: Request | None = None) -> str:
    if request is not None:
        h = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if h:
            h = h.split(":")[0]
            CONFIG["host"] = h
            return h
    return CONFIG.get("host", DEFAULT_HOST)

# تنظیمات لینک — این‌ها را می‌توانی همین‌جا تغییر دهی
LINK_SETTINGS = {
    "fp": "chrome",     # اثر انگشت: chrome / firefox / safari / random / خالی
    "alpn": "",         # خالی = بدون alpn (بهترین حالت برای Railway)
    "network": "ws",    # نوع شبکه
    "security": "tls",  # امنیت
}
SERVER_GEO = {"country": "", "code": "", "flag": ""}
def make_vless_link(uuid: str, host: str, label: str, port: int = 443, fp: str = "random", alpn: str = "", remark_override=None) -> str:
    path = f"/iliya/{uuid}"
    params = {"encryption": "none", "security": "tls", "type": "ws", "host": host, "path": path, "sni": host}
    if fp:
        params["fp"] = fp
    if alpn:
        params["alpn"] = alpn
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    if remark_override is not None:
        remark = quote(remark_override)
    else:
        name = ((SERVER_GEO.get("flag", "") + " " + SERVER_GEO.get("country", "")).strip()) or BRAND
        remark = quote(f"{name} | {label}")
    return f"vless://{uuid}@{host}:{port}?{query}#{remark}"
def _flag(code):
    code = (code or "").upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code)
async def detect_geo():
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get("http://ip-api.com/json/?fields=country,countryCode")
            if r.status_code == 200:
                d = r.json()
                SERVER_GEO["country"] = d.get("country", "") or ""
                SERVER_GEO["code"] = d.get("countryCode", "") or ""
                SERVER_GEO["flag"] = _flag(SERVER_GEO["code"])
    except Exception as e:
        log.warning("geo failed: " + str(e))
def sub_base64(links: list[str]) -> str:
    return base64.b64encode("\n".join(links).encode()).decode()
SUB_VARIANTS = FP_LIST = ["chrome", "firefox", "safari", "ios", "android", "edge", "360", "qq", "random", "randomized", ""]
ALPN_LIST = ["", "h2", "http/1.1", "h2,http/1.1"]
def _remaining_info(cfg):
    lim = int(cfg.get("limit_bytes", 0) or 0)
    used = int(cfg.get("used_bytes", 0) or 0)
    vol = "نامحدود" if lim <= 0 else fmt_bytes(max(0, lim - used))
    exp = cfg.get("expires_at")
    if not exp:
        days = "نامحدود"
    else:
        try:
            days = str(max(0, (datetime.fromisoformat(exp) - now()).days))
        except Exception:
            days = "?"
    return vol, days

def is_expired(cfg: dict) -> bool:
    exp = cfg.get("expires_at")
    if not exp:
        return False
    try:
        return now() > datetime.fromisoformat(exp)
    except Exception:
        return False


def is_allowed(cfg: dict | None) -> bool:
    if not cfg or not cfg.get("active", True):
        return False
    if is_expired(cfg):
        return False
    lim = cfg.get("limit_bytes", 0)
    if lim > 0 and cfg.get("used_bytes", 0) >= lim:
        return False
    return True


def public_config(uuid: str, cfg: dict, host: str) -> dict:
    lim = cfg.get("limit_bytes", 0)
    used = cfg.get("used_bytes", 0)
    return {
        "uuid": uuid,
        "label": cfg.get("label", ""),
        "owner": cfg.get("owner", BRAND),
        "active": cfg.get("active", True),
        "expired": is_expired(cfg),
        "allowed": is_allowed(cfg),
        "limit_bytes": lim,
        "used_bytes": used,
        "limit_fmt": "نامحدود" if lim == 0 else fmt_bytes(lim),
        "used_fmt": fmt_bytes(used),
        "percent": 0 if lim == 0 else min(100, round(used / lim * 100)),
        "expires_at": cfg.get("expires_at"),
        "ip_limit": cfg.get("ip_limit", 0),
        "is_test": cfg.get("is_test", False),
        "created_at": cfg.get("created_at"),
        "link": make_vless_link(uuid, host, cfg.get("label", BRAND)),
        "sub": f"https://{host}/sub/{uuid}",
    }


# ── محدودیت سرعت (Token Bucket) ─────────────────────────────────
class Bucket:
    __slots__ = ("rate", "cap", "tokens", "last")

    def __init__(self, rate: float):
        self.rate = max(rate, 1024)
        self.cap = max(self.rate, 16 * 1024)
        self.tokens = self.cap
        self.last = time.monotonic()

    async def take(self, n: int):
        while True:
            t = time.monotonic()
            self.tokens = min(self.cap, self.tokens + (t - self.last) * self.rate)
            self.last = t
            if self.tokens >= n:
                self.tokens -= n
                return
            await asyncio.sleep(min(max((n - self.tokens) / self.rate, 0.004), 0.5))


async def throttle(uuid: str, n: int):
    cfg = CONFIGS.get(uuid)
    rate = int((cfg or {}).get("speed_limit_bytes", 0) or 0)
    if rate <= 0 or n <= 0:
        return
    b = _buckets.get(uuid)
    if b is None or b.rate != max(rate, 1024):
        b = Bucket(rate)
        _buckets[uuid] = b
    await b.take(n)


# ── ذخیره‌سازی ──────────────────────────────────────────────
async def load_state():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if STATE_FILE.exists():
            async with aiofiles.open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.loads(await f.read())
            CONFIGS.update(data.get("configs", {}))
            if isinstance(data.get("link_settings"), dict):
                LINK_SETTINGS.update(data["link_settings"])
            if data.get("password_hash"):
                AUTH["password_hash"] = data["password_hash"]
            log.info(f"state loaded: {len(CONFIGS)} configs")
    except Exception as e:
        log.warning(f"load failed: {e}")
    if not AUTH["password_hash"]:
        AUTH["password_hash"] = hash_pw(ADMIN_PASSWORD)


async def save_state():
    async with SAVE_LOCK:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            data = {"configs": CONFIGS, "password_hash": AUTH["password_hash"],
                    "link_settings": LINK_SETTINGS, "saved_at": now().isoformat()}
            tmp = STATE_FILE.with_suffix(".tmp")
            async with aiofiles.open(tmp, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
            tmp.replace(STATE_FILE)
        except Exception as e:
            log.warning(f"save failed: {e}")


# ── احراز هویت داشبورد ──────────────────────────────────────
SESSION_COOKIE = "iliya_session"


def require_auth(request: Request):
    tok = request.cookies.get(SESSION_COOKIE)
    exp = SESSIONS.get(tok)
    if not tok or exp is None or exp < time.time():
        raise HTTPException(status_code=401, detail="unauthorized")
    return tok


def require_bot(x_bot_key: str = Header(default="")):
    if x_bot_key != BOT_API_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    return True


# ── ساخت کانفیگ (مشترک بین داشبورد و ربات) ──────────────────────
async def create_config(label: str, owner: str = BRAND, gb: float = 0,
                        days: int = 0, ip_limit: int = 0,
                        speed_mbit: float = 0, is_test: bool = False) -> dict:
    uuid = new_uuid()
    expires = (now() + timedelta(days=days)).isoformat() if days and days > 0 else None
    cfg = {
        "label": label or BRAND,
        "owner": owner or BRAND,
        "limit_bytes": int(gb * 1024 ** 3) if gb and gb > 0 else 0,
        "used_bytes": 0,
        "created_at": now().isoformat(),
        "expires_at": expires,
        "active": True,
        "ip_limit": int(ip_limit or 0),
        "speed_limit_bytes": int(speed_mbit * 1024 * 1024 / 8) if speed_mbit and speed_mbit > 0 else 0,
        "is_test": bool(is_test),
        "protocol": "vless-ws",
    }
    async with LOCK:
        CONFIGS[uuid] = cfg
    asyncio.create_task(save_state())
    log_act("config", f"کانفیگ «{cfg['label']}» برای {owner} ساخته شد", "ok")
    return {"uuid": uuid, **cfg}


# ═══════════════════  VLESS RELAY (WebSocket)  ═══════════════════
BUF = 1024 * 1024


def _ws_ip(ws: WebSocket) -> str:
    fwd = ws.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return ws.headers.get("x-real-ip") or (ws.client.host if ws.client else "?")


def parse_vless(chunk: bytes):
    """پارس هدر درخواست VLESS (طبق اسپک عمومی پروتکل)."""
    if len(chunk) < 24:
        raise ValueError("chunk too small")
    pos = 1 + 16                      # version(1) + uuid(16)
    addon = chunk[pos]; pos += 1 + addon
    cmd = chunk[pos]; pos += 1
    port = int.from_bytes(chunk[pos:pos + 2], "big"); pos += 2
    atype = chunk[pos]; pos += 1
    if atype == 1:
        addr = ".".join(str(b) for b in chunk[pos:pos + 4]); pos += 4
    elif atype == 2:
        dlen = chunk[pos]; pos += 1
        addr = chunk[pos:pos + dlen].decode("utf-8", "ignore"); pos += dlen
    elif atype == 3:
        ab = chunk[pos:pos + 16]; pos += 16
        addr = ":".join(f"{ab[i]:02x}{ab[i+1]:02x}" for i in range(0, 16, 2))
    else:
        raise ValueError("bad addr type")
    return cmd, addr, port, chunk[pos:]


async def count_use(uuid: str, n: int) -> bool:
    async with LOCK:
        cfg = CONFIGS.get(uuid)
        if not is_allowed(cfg):
            return False
        cfg["used_bytes"] += n
    STATS["total_bytes"] += n
    HOURLY[now().strftime("%H:00")] += n
    return True


def active_ips(uuid: str) -> set:
    return {c["ip"] for c in CONNS.values() if c.get("uuid") == uuid and c.get("ip")}


async def _up(ws, writer, cid, uuid):
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            data = msg.get("bytes") or (msg.get("text") or "").encode()
            if not data:
                continue
            if not await count_use(uuid, len(data)):
                await ws.close(code=1008, reason="quota")
                break
            await throttle(uuid, len(data))
            STATS["total_requests"] += 1
            CONNS[cid]["bytes"] += len(data)
            writer.write(data)
            if writer.transport.get_write_buffer_size() > BUF:
                await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.write_eof()
        except Exception:
            pass


async def _down(ws, reader, cid, uuid):
    first = True
    try:
        while True:
            data = await reader.read(BUF)
            if not data:
                break
            if not await count_use(uuid, len(data)):
                await ws.close(code=1008, reason="quota")
                break
            await throttle(uuid, len(data))
            CONNS[cid]["bytes"] += len(data)
            await ws.send_bytes((b"\x00\x00" + data) if first else data)
            first = False
    except Exception:
        pass


@app.websocket("/iliya/{uuid}")
async def ws_tunnel(ws: WebSocket, uuid: str):
    await ws.accept()
    cfg = CONFIGS.get(uuid)
    if not is_allowed(cfg):
        await ws.close(code=1008, reason="not authorized")
        return
    ip = _ws_ip(ws)
    lim = int(cfg.get("ip_limit", 0) or 0)
    if lim > 0 and ip not in active_ips(uuid) and len(active_ips(uuid)) >= lim:
        await ws.close(code=1008, reason="ip limit")
        return
    cid = secrets.token_urlsafe(6)
    CONNS[cid] = {"uuid": uuid, "ip": ip, "bytes": 0, "since": now().isoformat()}
    log_act("conn", f"اتصال جدید {ip} → {cfg.get('label','?')}", "info")
    writer = None
    try:
        first = await asyncio.wait_for(ws.receive(), timeout=15)
        if first["type"] == "websocket.disconnect":
            return
        chunk = first.get("bytes") or (first.get("text") or "").encode()
        cmd, addr, port, payload = parse_vless(chunk)
        if not await count_use(uuid, len(chunk)):
            await ws.close(code=1008, reason="quota")
            return
        reader, writer = await asyncio.wait_for(asyncio.open_connection(addr, port), timeout=10)
        s = writer.transport.get_extra_info("socket")
        if s:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if payload:
            writer.write(payload)
            await writer.drain()
        done, pending = await asyncio.wait(
            {asyncio.create_task(_up(ws, writer, cid, uuid)),
             asyncio.create_task(_down(ws, reader, cid, uuid))},
            return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        asyncio.create_task(save_state())
    except Exception as e:
        STATS["total_errors"] += 1
    finally:
        if writer:
            try:
                writer.close()
            except Exception:
                pass
        CONNS.pop(cid, None)


# ═══════════════════  ENDPOINTS  ══════════════════════════
@app.on_event("startup")
async def _startup():
    await load_state()
    await detect_geo()
    log_act("system", "سرور Iliya راه‌اندازی شد", "ok")
    log.info(f"Iliya Gateway up on :{PORT}")


@app.on_event("shutdown")
async def _shutdown():
    await save_state()


@app.get("/")
async def root():
    return {"service": BRAND, "status": "active"}


@app.get("/health")
async def health():
    return {"status": "ok", "connections": len(CONNS)}


# ── لاگین / لاگ‌آوت ─────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return login_html(BRAND)


@app.post("/api/login")
async def api_login(request: Request):
    body = await request.json()
    if hash_pw(body.get("password", "")) != AUTH["password_hash"]:
        raise HTTPException(status_code=401, detail="رمز اشتباه است")
    tok = secrets.token_urlsafe(32)
    SESSIONS[tok] = time.time() + 60 * 60 * 24 * 30
    resp = JSONResponse({"ok": True})
    resp.set_cookie(SESSION_COOKIE, tok, httponly=True, max_age=60 * 60 * 24 * 30, samesite="lax")
    return resp


@app.post("/api/logout")
async def api_logout(request: Request):
    SESSIONS.pop(request.cookies.get(SESSION_COOKIE), None)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.post("/api/change-password")
async def change_password(request: Request, _=Depends(require_auth)):
    body = await request.json()
    new = (body.get("password") or "").strip()
    if len(new) < 4:
        raise HTTPException(status_code=400, detail="رمز خیلی کوتاه است")
    AUTH["password_hash"] = hash_pw(new)
    await save_state()
    return {"ok": True}

@app.get("/api/settings")
async def get_settings(_=Depends(require_auth)):
    return {"link_settings": LINK_SETTINGS}

@app.post("/api/settings")
async def set_settings(request: Request):
    tok = request.cookies.get(SESSION_COOKIE)
    authed = tok in SESSIONS and SESSIONS.get(tok, 0) >= time.time()
    if not authed and request.headers.get("x-bot-key") != BOT_API_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    b = await request.json()
    for k in ("fp", "alpn", "network", "security"):
        if k in b:
            LINK_SETTINGS[k] = str(b.get(k) or "").strip()
    await save_state()
    return {"ok": True, "link_settings": LINK_SETTINGS}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return dashboard_html(BRAND)


# ── آمار ──────────────────────────────────────────────────
@app.get("/api/stats")
async def api_stats(request: Request, _=Depends(require_auth)):
    up = int(time.time() - STATS["start"])
    active = sum(1 for c in CONFIGS.values() if is_allowed(c))
    return {
        "total_configs": len(CONFIGS),
        "active_configs": active,
        "live_connections": len(CONNS),
        "total_bytes": STATS["total_bytes"],
        "total_bytes_fmt": fmt_bytes(STATS["total_bytes"]),
        "total_requests": STATS["total_requests"],
        "total_errors": STATS["total_errors"],
        "uptime": f"{up//3600:02d}:{(up%3600)//60:02d}:{up%60:02d}",
        "hourly": dict(HOURLY),
        "activity": list(ACTIVITY)[-30:][::-1],
    }


# ── CRUD کانفیگ (داشبورد) ─────────────────────────────────
@app.get("/api/configs")
async def list_configs(request: Request, _=Depends(require_auth)):
    host = get_host(request)
    items = [public_config(u, c, host) for u, c in CONFIGS.items()]
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"configs": items}


@app.post("/api/configs")
async def add_config(request: Request, _=Depends(require_auth)):
    b = await request.json()
    cfg = await create_config(
        label=(b.get("label") or "").strip()[:40] or f"{BRAND}-user",
        owner=(b.get("owner") or BRAND).strip()[:40],
        gb=float(b.get("gb", 0) or 0),
        days=int(b.get("days", 0) or 0),
        ip_limit=int(b.get("ip_limit", 0) or 0),
        speed_mbit=float(b.get("speed", 0) or 0),
    )
    host = get_host(request)
    return public_config(cfg["uuid"], CONFIGS[cfg["uuid"]], host)


@app.patch("/api/configs/{uuid}")
async def edit_config(uuid: str, request: Request, _=Depends(require_auth)):
    b = await request.json()
    async with LOCK:
        cfg = CONFIGS.get(uuid)
        if not cfg:
            raise HTTPException(status_code=404, detail="not found")
        if "active" in b:
            cfg["active"] = bool(b["active"])
        if "label" in b:
            cfg["label"] = str(b["label"])[:40]
        if "gb" in b:
            cfg["limit_bytes"] = int(float(b["gb"]) * 1024 ** 3) if float(b["gb"]) > 0 else 0
        if "add_days" in b and int(b["add_days"]) != 0:
            base = now()
            if cfg.get("expires_at"):
                try:
                    base = max(base, datetime.fromisoformat(cfg["expires_at"]))
                except Exception:
                    pass
            cfg["expires_at"] = (base + timedelta(days=int(b["add_days"]))).isoformat()
        if "reset_usage" in b and b["reset_usage"]:
            cfg["used_bytes"] = 0
        if "ip_limit" in b:
            cfg["ip_limit"] = int(b["ip_limit"] or 0)
        if "speed" in b:
            cfg["speed_limit_bytes"] = int(float(b["speed"]) * 1024 * 1024 / 8) if float(b["speed"]) > 0 else 0
            _buckets.pop(uuid, None)
    await save_state()
    host = get_host(request)
    return public_config(uuid, CONFIGS[uuid], host)


@app.delete("/api/configs/{uuid}")
async def del_config(uuid: str, request: Request, _=Depends(require_auth)):
    async with LOCK:
        CONFIGS.pop(uuid, None)
        _buckets.pop(uuid, None)
    await save_state()
    log_act("config", f"کانفیگ حذف شد: {uuid[:8]}", "warn")
    return {"ok": True}


# ── Subscription ────────────────────────────────────────────
@app.get("/sub/{uuid}")
async def subscription(uuid: str, request: Request):
    cfg = CONFIGS.get(uuid)
    if not cfg:
        raise HTTPException(status_code=404, detail="not found")
    host = get_host(request)
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(sub_page_html(BRAND, public_config(uuid, cfg, host)))
    if not is_allowed(cfg):
        raise HTTPException(status_code=404, detail="inactive")
    vol, days = _remaining_info(cfg)
    label = cfg.get("label", BRAND)
    links = [make_vless_link(uuid, host, label, remark_override="📊 حجم باقیمانده: " + vol), make_vless_link(uuid, host, label, remark_override="⏳ روز باقیمانده: " + days)]
    for i = 0
    for fp in FP_LIST:
        for alpn in ALPN_LIST:
            i += 1
            rk = str(i) + " · fp=" + (fp or "none") + " · alpn=" + (alpn or "none")
            links.append(make_vless_link(uuid, host, label, fp=fp, alpn=alpn, remark_override=rk))
    used = int(cfg.get("used_bytes", 0) or 0)
    total = int(cfg.get("limit_bytes", 0) or 0)
    expire = 0
    exp = cfg.get("expires_at")
    if exp:
        try:
            expire = int(datetime.fromisoformat(exp).timestamp())
        except Exception:
            expire = 0
    userinfo = "upload=0; download=" + str(used) + "; total=" + str(total) + "; expire=" + str(expire)
    title = base64.b64encode((BRAND + " | " + str(label)).encode()).decode()
    headers = {"subscription-userinfo": userinfo, "profile-update-interval": "12", "profile-title": "base64:" + title, "profile-web-page-url": "https://" + host + "/p/" + uuid}
    return Response(content=sub_base64(links), media_type="text/plain", headers=headers)
  
@app.get("/p/{uuid}", response_class=HTMLResponse)
async def public_page(uuid: str, request: Request):
    cfg = CONFIGS.get(uuid)
    if not cfg:
        raise HTTPException(status_code=404, detail="not found")
    host = get_host(request)
    return sub_page_html(BRAND, public_config(uuid, cfg, host))


# ── API ربات (ساخت/وضعیت کانفیگ) ────────────────────────────
@app.post("/api/bot/create")
async def bot_create(request: Request, _=Depends(require_bot)):
    b = await request.json()
    cfg = await create_config(
        label=(b.get("label") or f"{BRAND}-user").strip()[:40],
        owner=(b.get("owner") or BRAND).strip()[:60],
        gb=float(b.get("gb", 0) or 0),
        days=int(b.get("days", 0) or 0),
        ip_limit=int(b.get("users", b.get("ip_limit", 0)) or 0),
        speed_mbit=float(b.get("speed", 0) or 0),
        is_test=bool(b.get("is_test", False)),
    )
    host = b.get("host") or get_host(request)
    return public_config(cfg["uuid"], CONFIGS[cfg["uuid"]], host)


@app.get("/api/bot/config/{uuid}")
async def bot_config(uuid: str, request: Request, _=Depends(require_bot)):
    cfg = CONFIGS.get(uuid)
    if not cfg:
        raise HTTPException(status_code=404, detail="not found")
    return public_config(uuid, cfg, get_host(request))


@app.delete("/api/bot/config/{uuid}")
async def bot_del(uuid: str, _=Depends(require_bot)):
    async with LOCK:
        CONFIGS.pop(uuid, None)
    await save_state()
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, ws_ping_interval=None)

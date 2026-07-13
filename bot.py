# ==============================================================================
#  Iliya Config Bot  —  bot.py
#  ربات تلگرام فروش کانفیگ  |  بدون وابستگی به کتابخانه‌ی سنگین؛ فقط httpx + long polling
#
#  قابلیت‌ها:
#   • منوی شیشه‌ای/رنگی (ایموجی دار) مشابه عکس
#   • خرید کانفیگ با حجم/روز/کاربر دلخواه
#   • تست رایگان یک‌باره (1GB / 1روز / 1کاربر)
#   • کیف پول + ارسال رسید و تأیید دستی مدیر
#   • پنل مدیریت کامل برای ADMIN_IDS (مدیریت پلن‌ها، شارژ کیف پول، تأیید رسید، آمار، همگانی)
#   • خریدهای من ، حساب من ، دعوت دوستان ، آموزش‌ها ، پشتیبانی ، جست‌وجوی کانفیگ ، گردونه‌ی تخفیف
# ==============================================================================
import os
import json
import time
import random
import threading
import html
from datetime import datetime, timezone

import httpx

# ╔══════════════════════════════════════════════════════╗
# ║                     تنظیمات اصلی — اینجا را پر کنید                     ║
# ╚══════════════════════════════════════════════════════╝

# توکن ربات را از @BotFather بگیرید:
BOT_TOKEN = os.getenv("BOT_TOKEN", "8825265471:AAG7rqttcPs16NRH6ZjKWKVUd3Tq3TW2kqg")

# آیدی عددی مدیر(ان). از @userinfobot بگیرید. می‌توان چند نفر بود:
ADMIN_IDS = [2025464333]  # مثلاً: [123456789, 987654321]

# آدرس سرور Iliya Gateway (همان server.py که روی Railway دیپلوی می‌کنید):
SERVER_URL = os.getenv("SERVER_URL", "https://web-production-cd21b9.up.railway.app")

# کلید ارتباط ربات و سرور (باید دقیقاً با BOT_API_KEY در server.py یکی باشد):
BOT_API_KEY = os.getenv("BOT_API_KEY", "iliya-secret-bridge")

# اطلاعات پرداخت / پشتیبانی:
CARD_NUMBER = os.getenv("CARD_NUMBER", "6037-XXXX-XXXX-XXXX")
CARD_HOLDER = os.getenv("CARD_HOLDER", "ایلیا")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@Iliya_Support")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@Iliya_VPN")
BRAND = os.getenv("BRAND", "Iliya")

# میزبانی که در لینک کانفیگ قرار می‌گیرد (خالی = دامنه‌ی خود سرور):
CONFIG_HOST = os.getenv("CONFIG_HOST", "")

# پاداش دعوت دوستان (تومان به ازای هر زیرمجموعه‌ی خریددار):
REFERRAL_REWARD = int(os.getenv("REFERRAL_REWARD", "10000"))

DATA_DIR = os.getenv("DATA_DIR", ".")
STATE_FILE = os.path.join(DATA_DIR, "iliya_bot.json")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# پلن‌های پیش‌فرض (مدیر می‌تواند از پنل تغییر دهد):
DEFAULT_PLANS = [
    {"id": "p1", "title": "🥉 اقتصادی", "gb": 30, "days": 30, "users": 1, "price": 75000},
    {"id": "p2", "title": "🔥 حرفه‌ای", "gb": 60, "days": 30, "users": 2, "price": 135000},
    {"id": "p3", "title": "💎 نامحدود", "gb": 0, "days": 30, "users": 3, "price": 220000},
    {"id": "p4", "title": "🏢 سازمانی", "gb": 200, "days": 60, "users": 5, "price": 420000},
]

# مقادیر گردونه‌ی تخفیف (تومان شارژ کیف پول):
WHEEL_PRIZES = [0, 2000, 5000, 0, 10000, 3000, 0, 15000]

# ───────────────────────── مدیریت وضعیت (ذخیره در JSON) ───────────────
LOCK = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat()


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"users": {}, "plans": DEFAULT_PLANS, "pending_receipts": {}, "settings": {}}


def save_state(s):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


STATE = load_state()
    
def get_user(uid, name="", ref=None):
    uid = str(uid)
    u = STATE["users"].get(uid)
    if not u:
        u = {
            "id": uid, "name": name, "wallet": 0, "configs": [],
            "test_used": False, "joined": _now(), "ref_by": ref,
            "invited": [], "step": None, "buf": {},
        }
        STATE["users"][uid] = u
        # پاداش دعوت
        if ref and str(ref) in STATE["users"] and str(ref) != uid:
            inviter = STATE["users"][str(ref)]
            if uid not in inviter.get("invited", []):
                inviter.setdefault("invited", []).append(uid)
        save_state(STATE)
    if name and u.get("name") != name:
        u["name"] = name
    return u


def fmt_toman(n):
    try:
        return f"{int(n):,} تومان"
    except Exception:
        return f"{n} تومان"


# ──────────────────────────────── ارتباط با تلگرام ────────────────────
HTTP = httpx.Client(timeout=65)


def tg(method, **params):
    try:
        r = HTTP.post(f"{API}/{method}", json=params)
        return r.json()
    except Exception as e:
        print("tg error:", method, e)
        return {"ok": False}


def send(chat_id, text, kb=None, preview=False):
    p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
         "disable_web_page_preview": not preview}
    if kb is not None:
        p["reply_markup"] = {"inline_keyboard": kb}
    return tg("sendMessage", **p)


def edit(chat_id, mid, text, kb=None):
    p = {"chat_id": chat_id, "message_id": mid, "text": text,
         "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb is not None:
        p["reply_markup"] = {"inline_keyboard": kb}
    return tg("editMessageText", **p)


def answer_cb(cb_id, text="", alert=False):
    tg("answerCallbackQuery", callback_query_id=cb_id, text=text, show_alert=alert)


def btn(text, data):
    return {"text": text, "callback_data": data}


def url_btn(text, url):
    return {"text": text, "url": url}


# ─────────────────────────────── کیبوردها (دکمه‌های رنگی/ایموجی‌دار) ─────────
def main_menu(uid):
    is_admin = int(uid) in ADMIN_IDS
    kb = [
        [btn("🎡 گردونه تخفیف", "wheel")],
        [btn("🛒 خرید کانفیگ", "buy"), btn("📦 خریدهای من", "mycfg")],
        [btn("🧾 ارسال رسید – شارژ کیف پول", "charge")],
        [btn("🆓 تست رایگان [ قبل خرید الزامی ]", "test")],
        [btn("👤 حساب من", "me"), btn("🤝 دعوت دوستان", "ref")],
        [btn("📚 آموزش‌ها", "help"), btn("🆘 پشتیبانی", "support")],
        [btn("🔍 جست‌وجوی کانفیگ", "find")],
    ]
    if is_admin:
        kb.append([btn("⚙️ پنل مدیریت", "admin")])
    return kb


def back_btn(to="home"):
    return [btn("🔙 بازگشت", to)]


def welcome_text(u):
    return (
        f"🌟 <b>به ربات {BRAND} خوش آمدید!</b>\n\n"
        f"🚀 خرید سریع، پایدار و پرسرعت کانفیگ\n"
        f"💳 موجودی کیف پول: <b>{fmt_toman(u['wallet'])}</b>\n"
        f"📦 کانفیگ‌های فعال: <b>{len(u['configs'])}</b>\n\n"
        f"👇 از منوی زیر یک گزینه را انتخاب کنید:"
    )


# ────────────────────────────── ارتباط با سرور (ساخت/حذف کانفیگ) ────────
def server_create(label, owner, gb, days, users, speed=0, is_test=False):
    """کانفیگ را روی سرور Iliya Gateway می‌سازد و دیکشنری عمومی برمی‌گرداند."""
    try:
        r = HTTP.post(
            f"{SERVER_URL}/api/bot/create",
            headers={"X-Bot-Key": BOT_API_KEY},
            json={"label": label, "owner": owner, "gb": gb, "days": days,
                  "users": users, "speed": speed, "is_test": is_test,
                  "host": CONFIG_HOST},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()
        print("server_create failed:", r.status_code, r.text)
    except Exception as e:
        print("server_create error:", e)
    return None


def server_get_settings():
    try:
        r = HTTP.get(SERVER_URL + "/api/settings",
                     headers={"X-Bot-Key": BOT_API_KEY}, timeout=15)
        if r.status_code == 200:
            return r.json().get("link_settings", {})
    except Exception as e:
        print("get_settings error:", e)
    return {}

def server_set_settings(**kw):
    try:
        r = HTTP.post(SERVER_URL + "/api/settings",
                      headers={"X-Bot-Key": BOT_API_KEY}, json=kw, timeout=15)
        if r.status_code == 200:
            return r.json().get("link_settings", {})
    except Exception as e:
        print("set_settings error:", e)
    return None


def server_delete(uuid):
    try:
        HTTP.request("DELETE", f"{SERVER_URL}/api/bot/config/{uuid}",
                     headers={"X-Bot-Key": BOT_API_KEY}, timeout=20)
    except Exception as e:
        print("server_delete error:", e)


def config_caption(cfg, title="✅ کانفیگ شما آماده است"):
    link = cfg.get("link", "")
    sub = cfg.get("sub", "")
    return (
        f"{title}\n\n"
        f"🏷 <b>نام:</b> {html.escape(str(cfg.get('label','')))}\n"
        f"📊 <b>حجم:</b> {cfg.get('limit_fmt','نامحدود')}\n"
        f"⏳ <b>انقضا:</b> {(cfg.get('expires_at') or 'دائمی')[:10]}\n"
        f"👥 <b>کاربر:</b> {cfg.get('ip_limit') or 'نامحدود'}\n\n"
        f"🔗 <b>لینک اتصال (کپی کنید):</b>\n<code>{html.escape(link)}</code>\n\n"
        f"🌐 <b>صفحه مدیریت:</b>\n{sub}"
    )


# ──────────────────────────────── پردازش دستورات ────────────────────
def handle_start(msg):
    uid = msg["from"]["id"]
    name = msg["from"].get("first_name", "")
    ref = None
    parts = (msg.get("text") or "").split()
    if len(parts) > 1 and parts[1].isdigit():
        ref = parts[1]
    with LOCK:
        u = get_user(uid, name, ref)
        u["step"] = None
        save_state(STATE)
    send(msg["chat"]["id"], welcome_text(u), main_menu(uid))


def show_home(chat_id, uid, mid=None):
    with LOCK:
        u = get_user(uid)
        u["step"] = None
        save_state(STATE)
    if mid:
        edit(chat_id, mid, welcome_text(u), main_menu(uid))
    else:
        send(chat_id, welcome_text(u), main_menu(uid))


def show_buy(chat_id, uid, mid):
    kb = []
    for p in STATE["plans"]:
        vol = "نامحدود" if not p["gb"] else f"{p['gb']}GB"
        kb.append([btn(f"{p['title']} | {vol} | {p['days']}روز | {fmt_toman(p['price'])}", f"plan:{p['id']}")])
    kb.append(back_btn("home"))
    txt = ("🛒 <b>خرید کانفیگ</b>\n\n"
           "یکی از پلن‌های زیر را انتخاب کنید. مبلغ از کیف پول شما کسر می‌شود.\n"
           "💡 اگر موجودی کافی ندارید، ابتدا کیف پول را شارژ کنید.")
    edit(chat_id, mid, txt, kb)


def do_purchase(chat_id, uid, plan_id, cb_id):
    with LOCK:
        u = get_user(uid)
        plan = next((p for p in STATE["plans"] if p["id"] == plan_id), None)
        if not plan:
            answer_cb(cb_id, "پلن یافت نشد", True)
            return
        if u["wallet"] < plan["price"]:
            answer_cb(cb_id, "⚠️ موجودی کیف پول کافی نیست. ابتدا شارژ کنید.", True)
            return
    answer_cb(cb_id, "⏳ در حال ساخت کانفیگ...")
    label = f"{u.get('name','user')}-{plan['title'].split()[-1]}"
    cfg = server_create(label, BRAND, plan["gb"], plan["days"], plan["users"])
    if not cfg:
        send(chat_id, "❌ خطا در ساخت کانفیگ. لطفاً با پشتیبانی تماس بگیرید.", [back_btn("home")])
        return
    with LOCK:
        u["wallet"] -= plan["price"]
        u["configs"].append({"uuid": cfg["uuid"], "label": cfg.get("label"),
                             "plan": plan["title"], "date": _now(), "is_test": False})
        # پاداش دعوت برای معرف‌کننده در اولین خرید
        if u.get("ref_by") and not u.get("ref_rewarded"):
            inv = STATE["users"].get(str(u["ref_by"]))
            if inv:
                inv["wallet"] += REFERRAL_REWARD
                u["ref_rewarded"] = True
                send(inv["id"], f"🎉 یکی از زیرمجموعه‌های شما خرید کرد! \n💰 {fmt_toman(REFERRAL_REWARD)} به کیف پول شما اضافه شد.")
        save_state(STATE)
    send(chat_id, config_caption(cfg, "🎉 <b>خرید موفق بود!</b>"), [back_btn("home")])


def do_test(chat_id, uid, cb_id):
    with LOCK:
        u = get_user(uid)
        if u.get("test_used"):
            answer_cb(cb_id, "⚠️ شما قبلاً از تست رایگان استفاده کرده‌اید.", True)
            return
    answer_cb(cb_id, "⏳ در حال ساخت کانفیگ تست...")
    cfg = server_create(f"{u.get('name','user')}-Test", BRAND, 1, 1, 1, is_test=True)
    if not cfg:
        send(chat_id, "❌ خطا در ساخت کانفیگ تست.", [back_btn("home")])
        return
    with LOCK:
        u["test_used"] = True
        u["configs"].append({"uuid": cfg["uuid"], "label": cfg.get("label"),
                             "plan": "🧪 تست رایگان", "date": _now(), "is_test": True})
        save_state(STATE)
    send(chat_id, config_caption(cfg, "🧪 <b>کانفیگ تست رایگان (1گیگ / 1روز / 1کاربر)</b>\n⚠️ فقط یک‌بار قابل دریافت است."), [back_btn("home")])


def show_mycfg(chat_id, uid, mid):
    u = get_user(uid)
    if not u["configs"]:
        edit(chat_id, mid, "📦 هنوز کانفیگی ندارید.\nاز بخش «خرید کانفیگ» یا «تست رایگان» شروع کنید.", [back_btn("home")])
        return
    kb = []
    for c in u["configs"][-20:]:
        kb.append([btn(f"{c.get('plan','کانفیگ')} — {c.get('label','')}", f"cfg:{c['uuid']}")])
    kb.append(back_btn("home"))
    edit(chat_id, mid, "📦 <b>خریدهای من</b>\n\nبرای مشاهده‌ی جزئیات و لینک، روی هر کانفیگ بزنید:", kb)


def show_cfg_detail(chat_id, uid, uuid, mid):
    try:
        r = HTTP.get(f"{SERVER_URL}/api/bot/config/{uuid}",
                     headers={"X-Bot-Key": BOT_API_KEY}, timeout=20)
        cfg = r.json() if r.status_code == 200 else None
    except Exception:
        cfg = None
    if not cfg:
        edit(chat_id, mid, "❌ این کانفیگ دیگر موجود نیست.", [back_btn("mycfg")])
        return
    edit(chat_id, mid, config_caption(cfg, "🔌 <b>جزئیات کانفیگ</b>"), [back_btn("mycfg")])


def show_charge(chat_id, uid, mid):
    txt = ("🧾 <b>شارژ کیف پول</b>\n\n"
           f"💳 مبلغ دلخواه را به کارت زیر واریز کنید:\n\n"
           f"🔢 <code>{CARD_NUMBER}</code>\n"
           f"👤 به نام: <b>{CARD_HOLDER}</b>\n\n"
           "📸 سپس <b>عکس رسید</b> را همینجا ارسال کنید.\n"
           "پس از تأیید مدیر، مبلغ به کیف پول شما اضافه می‌شود.")
    with LOCK:
        u = get_user(uid)
        u["step"] = "await_receipt"
        save_state(STATE)
    edit(chat_id, mid, txt, [back_btn("home")])


def handle_receipt_photo(msg):
    uid = msg["from"]["id"]
    u = get_user(uid)
    if u.get("step") != "await_receipt":
        return False
    file_id = msg["photo"][-1]["file_id"]
    rid = f"r{int(time.time())}{uid}"
    with LOCK:
        STATE["pending_receipts"][rid] = {"uid": str(uid), "name": u.get("name", ""),
                                          "file_id": file_id, "time": _now()}
        u["step"] = None
        save_state(STATE)
    send(msg["chat"]["id"], "✅ رسید شما دریافت شد و برای مدیر ارسال گردید.\nپس از تأیید، کیف پول شما شارژ می‌شود.", [back_btn("home")])
    cap = (f"🧾 <b>رسید جدید</b>\n\nاز: {html.escape(u.get('name',''))}\n🆔 <code>{uid}</code>\n\nمبلغ را تأیید کنید:")
    kb = [[btn("✅ تأیید و شارژ", f"rok:{rid}"), btn("❌ رد", f"rno:{rid}")]]
    for aid in ADMIN_IDS:
        tg("sendPhoto", chat_id=aid, photo=file_id, caption=cap,
           parse_mode="HTML", reply_markup={"inline_keyboard": kb})
    return True


def show_me(chat_id, uid, mid):
    u = get_user(uid)
    txt = ("👤 <b>حساب من</b>\n\n"
           f"🆔 شناسه: <code>{uid}</code>\n"
           f"👑 نام: {html.escape(u.get('name',''))}\n"
           f"💰 کیف پول: <b>{fmt_toman(u['wallet'])}</b>\n"
           f"📦 تعداد کانفیگ: <b>{len(u['configs'])}</b>\n"
           f"🤝 دعوت‌شدگان: <b>{len(u.get('invited',[]))}</b>\n"
           f"🧪 تست رایگان: {'استفاده شده' if u.get('test_used') else 'موجود'}")
    edit(chat_id, mid, txt, [[btn("🧾 شارژ کیف پول", "charge")], back_btn("home")])


def show_ref(chat_id, uid, mid):
    me = tg("getMe").get("result", {})
    uname = me.get("username", "")
    link = f"https://t.me/{uname}?start={uid}"
    u = get_user(uid)
    txt = ("🤝 <b>دعوت دوستان</b>\n\n"
           f"به ازای هر دوستی که با لینک شما عضو شود و خرید کند، "
           f"<b>{fmt_toman(REFERRAL_REWARD)}</b> هدیه می‌گیرید!\n\n"
           f"🔗 لینک اختصاصی شما:\n<code>{link}</code>\n\n"
           f"👥 تاکنون <b>{len(u.get('invited',[]))}</b> نفر دعوت کرده‌اید.")
    edit(chat_id, mid, txt, [back_btn("home")])


def show_help(chat_id, uid, mid):
    txt = ("📚 <b>آموزش اتصال</b>\n\n"
           "1️⃣ یکی از اپ‌های زیر را نصب کنید:\n"
           "   • <b>Android:</b> v2rayNG\n"
           "   • <b>iOS:</b> V2Box / Streisand\n"
           "   • <b>Windows:</b> v2rayN\n\n"
           "2️⃣ لینک کانفیگ را کپی کنید.\n"
           "3️⃣ در اپ، گزینه‌ی «Import from clipboard» را بزنید.\n"
           "4️⃣ متصل شوید و لذت ببرید! 🚀\n\n"
           f"❓ سوالی دارید؟ {SUPPORT_USERNAME}")
    edit(chat_id, mid, txt, [back_btn("home")])


def show_support(chat_id, uid, mid):
    kb = [[url_btn("💬 گفتگو با پشتیبانی", f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")],
          [url_btn("📢 کانال ما", f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
          back_btn("home")]
    edit(chat_id, mid, f"🆘 <b>پشتیبانی {BRAND}</b>\n\nتیم پشتیبانی ما ۲۴ ساعته پاسخگوی شماست.", kb)


def show_find(chat_id, uid, mid):
    with LOCK:
        u = get_user(uid)
        u["step"] = "await_search"
        save_state(STATE)
    edit(chat_id, mid, "🔍 <b>جست‌وجوی کانفیگ</b>\n\nشناسه (UUID) یا نام کانفیگ را بفرستید:", [back_btn("home")])


def handle_search_text(msg):
    uid = msg["from"]["id"]
    u = get_user(uid)
    if u.get("step") != "await_search":
        return False
    q = (msg.get("text") or "").strip()
    with LOCK:
        u["step"] = None
        save_state(STATE)
    match = None
    for c in u["configs"]:
        if q.lower() in (c.get("uuid", "") + " " + (c.get("label") or "")).lower():
            match = c
            break
    if not match:
        send(msg["chat"]["id"], "❌ کانفیگی با این مشخصات در حساب شما یافت نشد.", [back_btn("home")])
        return True
    try:
        r = HTTP.get(f"{SERVER_URL}/api/bot/config/{match['uuid']}",
                     headers={"X-Bot-Key": BOT_API_KEY}, timeout=20)
        cfg = r.json() if r.status_code == 200 else None
    except Exception:
        cfg = None
    if cfg:
        send(msg["chat"]["id"], config_caption(cfg, "🔍 <b>کانفیگ پیدا شد</b>"), [back_btn("home")])
    else:
        send(msg["chat"]["id"], "❌ کانفیگ دیگر روی سرور موجود نیست.", [back_btn("home")])
    return True


def do_wheel(chat_id, uid, cb_id, mid):
    with LOCK:
        u = get_user(uid)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if u.get("wheel_day") == today:
            answer_cb(cb_id, "⚠️ امروز گردونه را چرخانده‌اید. فردا دوباره تلاش کنید!", True)
            return
        prize = random.choice(WHEEL_PRIZES)
        u["wheel_day"] = today
        u["wallet"] += prize
        save_state(STATE)
    if prize:
        answer_cb(cb_id, f"🎉 تبریک! {fmt_toman(prize)} برنده شدید!", True)
    else:
        answer_cb(cb_id, "😅 این بار شانس نیاوردید. فردا دوباره!", True)
    show_home(chat_id, uid, mid)


# ─────────────────────────────────── پنل مدیریت ────────────────────────
def is_admin(uid):
    return int(uid) in ADMIN_IDS

def show_admin_settings(chat_id, uid, mid):
    if not is_admin(uid):
        return
    s = server_get_settings()
    fp = s.get("fp") or "—"
    alpn = s.get("alpn") or "بدون (خالی)"
    net = s.get("network") or "ws"
    sec = s.get("security") or "tls"
    txt = ("🎨 تنظیمات کانفیگ \n\n"
           "روی همه‌ی کانفیگ‌های جدید اعمال می‌شود:\n\n"
           "🔹 اثر انگشت: " + fp + "\n"
           "🔹 alpn: " + alpn + "\n"
           "🔹 شبکه: " + net + " | امنیت: " + sec + "\n\n"
           "برای تغییر، یکی را انتخاب کنید:")
    kb = [
        [btn("اثرانگشت: Chrome", "setfp:chrome"), btn("Firefox", "setfp:firefox")],
        [btn("Safari", "setfp:safari"), btn("Random", "setfp:random"), btn("بدون", "setfp:")],
        [btn("alpn: بدون (پیشنهادی)", "setalpn:"), btn("http/1.1", "setalpn:http/1.1")],
        back_btn("admin"),
    ]
    edit(chat_id, mid, txt, kb)


def show_admin(chat_id, uid, mid):
    if not is_admin(uid):
        return
    total_users = len(STATE["users"])
    total_wallet = sum(x.get("wallet", 0) for x in STATE["users"].values())
    pend = len(STATE["pending_receipts"])
    txt = ("⚙️ <b>پنل مدیریت Iliya</b>\n\n"
           f"👥 کاربران: <b>{total_users}</b>\n"
           f"💰 مجموع کیف پول‌ها: <b>{fmt_toman(total_wallet)}</b>\n"
           f"🧾 رسیدهای در انتظار: <b>{pend}</b>\n"
           f"📦 تعداد پلن‌ها: <b>{len(STATE['plans'])}</b>")
    kb = [
        [btn("💳 شارژ دستی کیف پول", "a_charge"), btn("🧾 رسیدها", "a_receipts")],
        [btn("📦 مدیریت پلن‌ها", "a_plans"), btn("👤 جست‌وجوی کاربر", "a_finduser")],
        [btn("📢 پیام همگانی", "a_broadcast"), btn("📊 آمار کامل", "a_stats")],
        back_btn("home"),
    ]
    edit(chat_id, mid, txt, kb)


def show_admin_receipts(chat_id, uid, mid):
    if not is_admin(uid):
        return
    if not STATE["pending_receipts"]:
        edit(chat_id, mid, "🧾 رسیدی در انتظار تأیید نیست.", [back_btn("admin")])
        return
    kb = []
    for rid, r in list(STATE["pending_receipts"].items())[:15]:
        kb.append([btn(f"🧾 {r.get('name','')} ({r['uid']})", f"rshow:{rid}")])
    kb.append(back_btn("admin"))
    edit(chat_id, mid, "🧾 <b>رسیدهای در انتظار</b>\nبرای دیدن و تأیید روی هرکدام بزنید:", kb)


def admin_charge_prompt(chat_id, uid, mid):
    if not is_admin(uid):
        return
    with LOCK:
        u = get_user(uid)
        u["step"] = "admin_charge"
        save_state(STATE)
    edit(chat_id, mid, "💳 <b>شارژ دستی</b>\n\nشناسه کاربر و مبلغ را با فاصله بفرستید.\nمثال: <code>123456789 50000</code>\n(مبلغ منفی = کسر)", [back_btn("admin")])


def admin_broadcast_prompt(chat_id, uid, mid):
    if not is_admin(uid):
        return
    with LOCK:
        u = get_user(uid)
        u["step"] = "admin_broadcast"
        save_state(STATE)
    edit(chat_id, mid, "📢 <b>پیام همگانی</b>\n\nمتن پیامی که برای همه‌ی کاربران ارسال می‌شود را بفرستید:", [back_btn("admin")])


def admin_finduser_prompt(chat_id, uid, mid):
    if not is_admin(uid):
        return
    with LOCK:
        u = get_user(uid)
        u["step"] = "admin_finduser"
        save_state(STATE)
    edit(chat_id, mid, "👤 <b>جست‌وجوی کاربر</b>\n\nشناسه‌ی عددی کاربر را بفرستید:", [back_btn("admin")])


def admin_plans(chat_id, uid, mid):
    if not is_admin(uid):
        return
    txt = "📦 <b>پلن‌های فعلی</b>\n\n"
    for p in STATE["plans"]:
        vol = "نامحدود" if not p["gb"] else f"{p['gb']}GB"
        txt += f"• {p['title']} | {vol} | {p['days']}روز | {p['users']}کاربر | {fmt_toman(p['price'])}\n"
    txt += ("\n➕ برای افزودن/ویرایش پلن، در قالب زیر بفرستید:\n"
            "<code>عنوان | حجمGB | روز | کاربر | قیمت</code>\n"
            "مثال: <code>طلایی | 100 | 30 | 3 | 300000</code>\n"
            "(حجم 0 = نامحدود)")
    with LOCK:
        u = get_user(uid)
        u["step"] = "admin_addplan"
        save_state(STATE)
    kb = [[btn("🗑 حذف یک پلن", "a_delplan")], back_btn("admin")]
    edit(chat_id, mid, txt, kb)


def admin_delplan_menu(chat_id, uid, mid):
    if not is_admin(uid):
        return
    kb = [[btn(f"🗑 {p['title']}", f"delplan:{p['id']}")] for p in STATE["plans"]]
    kb.append(back_btn("admin"))
    with LOCK:
        u = get_user(uid)
        u["step"] = None
        save_state(STATE)
    edit(chat_id, mid, "🗑 کدام پلن حذف شود؟", kb)


def admin_stats(chat_id, uid, mid):
    if not is_admin(uid):
        return
    users = STATE["users"].values()
    total_cfg = sum(len(x.get("configs", [])) for x in users)
    tests = sum(1 for x in users if x.get("test_used"))
    try:
        r = HTTP.get(f"{SERVER_URL}/health", timeout=10)
        srv = "🟢 آنلاین" if r.status_code == 200 else "🔴 خطا"
    except Exception:
        srv = "🔴 اتصال نشد"
    txt = ("📊 <b>آمار کامل</b>\n\n"
           f"👥 کاربران: {len(STATE['users'])}\n"
           f"📦 کل کانفیگ‌ها: {total_cfg}\n"
           f"🧪 تست‌های استفاده‌شده: {tests}\n"
           f"🖥 وضعیت سرور: {srv}")
    edit(chat_id, mid, txt, [back_btn("admin")])


def approve_receipt(chat_id, uid, rid, cb_id, mid):
    if not is_admin(uid):
        return
    with LOCK:
        r = STATE["pending_receipts"].get(rid)
        if not r:
            answer_cb(cb_id, "این رسید قبلاً رسیدگی شده.", True)
            return
        u = get_user(uid)
        u["step"] = "admin_approve:" + rid
        save_state(STATE)
    answer_cb(cb_id, "مبلغ را وارد کنید")
    send(chat_id, f"💰 مبلغ شارژ برای کاربر <code>{r['uid']}</code> را به تومان بفرستید:")


def reject_receipt(chat_id, uid, rid, cb_id):
    if not is_admin(uid):
        return
    with LOCK:
        r = STATE["pending_receipts"].pop(rid, None)
        save_state(STATE)
    answer_cb(cb_id, "رسید رد شد")
    if r:
        send(r["uid"], "❌ متأسفانه رسید شما تأیید نشد. در صورت اشتباه با پشتیبانی تماس بگیرید.")


# ────────────────────────── پردازش پیام‌های متنی مدیر ────────────────
def handle_admin_text(msg):
    uid = msg["from"]["id"]
    if not is_admin(uid):
        return False
    u = get_user(uid)
    step = u.get("step") or ""
    text = (msg.get("text") or "").strip()
    cid = msg["chat"]["id"]

    if step == "admin_charge":
        parts = text.split()
        if len(parts) != 2 or not parts[0].isdigit():
            send(cid, "⚠️ قالب اشتباه است. مثال: <code>123456789 50000</code>")
            return True
        target, amount = parts[0], int(parts[1])
        with LOCK:
            tu = get_user(target)
            tu["wallet"] += amount
            u["step"] = None
            save_state(STATE)
        send(cid, f"✅ کیف پول کاربر {target} به {fmt_toman(tu['wallet'])} رسید.")
        send(target, f"💰 کیف پول شما {fmt_toman(amount)} شارژ شد.\nموجودی جدید: {fmt_toman(tu['wallet'])}")
        return True

    if step.startswith("admin_approve:"):
        rid = step.split(":", 1)[1]
        if not text.lstrip("-").isdigit():
            send(cid, "⚠️ لطفاً فقط عدد (تومان) بفرستید.")
            return True
        amount = int(text)
        with LOCK:
            r = STATE["pending_receipts"].pop(rid, None)
            u["step"] = None
            if r:
                tu = get_user(r["uid"])
                tu["wallet"] += amount
            save_state(STATE)
        if r:
            send(cid, f"✅ کیف پول کاربر {r['uid']} شارژ شد.")
            send(r["uid"], f"✅ رسید شما تأیید شد!\n💰 {fmt_toman(amount)} به کیف پول شما اضافه شد.")
        return True

    if step == "admin_broadcast":
        with LOCK:
            u["step"] = None
            save_state(STATE)
        sent = 0
        for tid in list(STATE["users"].keys()):
            res = send(tid, f"📢 <b>پیام از {BRAND}</b>\n\n{html.escape(text)}")
            if res.get("ok"):
                sent += 1
            time.sleep(0.05)
        send(cid, f"✅ پیام برای {sent} کاربر ارسال شد.")
        return True

    if step == "admin_finduser":
        with LOCK:
            u["step"] = None
            save_state(STATE)
        tu = STATE["users"].get(text)
        if not tu:
            send(cid, "❌ کاربری با این شناسه یافت نشد.")
            return True
        info = (f"👤 <b>کاربر {text}</b>\n\n"
                f"👑 نام: {html.escape(tu.get('name',''))}\n"
                f"💰 کیف پول: {fmt_toman(tu.get('wallet',0))}\n"
                f"📦 کانفیگ‌ها: {len(tu.get('configs',[]))}\n"
                f"🧪 تست: {'بله' if tu.get('test_used') else 'خیر'}\n"
                f"🤝 دعوت‌شدگان: {len(tu.get('invited',[]))}")
        send(cid, info)
        return True

    if step == "admin_addplan":
        parts = [x.strip() for x in text.split("|")]
        if len(parts) != 5:
            send(cid, "⚠️ قالب اشتباه است. مثال: <code>طلایی | 100 | 30 | 3 | 300000</code>")
            return True
        try:
            title, gb, days, users, price = parts[0], int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
        except ValueError:
            send(cid, "⚠️ اعداد نامعتبرند.")
            return True
        with LOCK:
            pid = f"p{int(time.time())}"
            STATE["plans"].append({"id": pid, "title": title, "gb": gb, "days": days,
                                   "users": users, "price": price})
            u["step"] = None
            save_state(STATE)
        send(cid, f"✅ پلن «{html.escape(title)}» اضافه شد.")
        return True

    return False


# ──────────────────────────────── مسیریاب اصلی callback ─────────────────
def on_callback(cb):
    data = cb.get("data", "")
    uid = cb["from"]["id"]
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    mid = msg.get("message_id")
    cb_id = cb["id"]
    get_user(uid, cb["from"].get("first_name", ""))

    simple = {
        "home": lambda: show_home(chat_id, uid, mid),
        "buy": lambda: show_buy(chat_id, uid, mid),
        "mycfg": lambda: show_mycfg(chat_id, uid, mid),
        "charge": lambda: show_charge(chat_id, uid, mid),
        "me": lambda: show_me(chat_id, uid, mid),
        "ref": lambda: show_ref(chat_id, uid, mid),
        "help": lambda: show_help(chat_id, uid, mid),
        "support": lambda: show_support(chat_id, uid, mid),
        "find": lambda: show_find(chat_id, uid, mid),
        "admin": lambda: show_admin(chat_id, uid, mid),
        "a_receipts": lambda: show_admin_receipts(chat_id, uid, mid),
        "a_charge": lambda: admin_charge_prompt(chat_id, uid, mid),
        "a_broadcast": lambda: admin_broadcast_prompt(chat_id, uid, mid),
        "a_finduser": lambda: admin_finduser_prompt(chat_id, uid, mid),
        "a_plans": lambda: admin_plans(chat_id, uid, mid),
        "a_delplan": lambda: admin_delplan_menu(chat_id, uid, mid),
        "a_stats": lambda: admin_stats(chat_id, uid, mid),
    }
    if data in simple:
        answer_cb(cb_id)
        simple[data]()
        return
    if data == "wheel":
        do_wheel(chat_id, uid, cb_id, mid)
        return
    if data == "test":
        do_test(chat_id, uid, cb_id)
        return
    if data.startswith("plan:"):
        do_purchase(chat_id, uid, data.split(":", 1)[1], cb_id)
        return
    if data.startswith("cfg:"):
        answer_cb(cb_id)
        show_cfg_detail(chat_id, uid, data.split(":", 1)[1], mid)
        return
    if data.startswith("rshow:"):
        rid = data.split(":", 1)[1]
        r = STATE["pending_receipts"].get(rid)
        answer_cb(cb_id)
        if r:
            kb = [[btn("✅ تأیید و شارژ", f"rok:{rid}"), btn("❌ رد", f"rno:{rid}")]]
            tg("sendPhoto", chat_id=chat_id, photo=r["file_id"],
               caption=f"🧾 رسید {html.escape(r.get('name',''))} (<code>{r['uid']}</code>)",
               parse_mode="HTML", reply_markup={"inline_keyboard": kb})
        return
    if data.startswith("rok:"):
        approve_receipt(chat_id, uid, data.split(":", 1)[1], cb_id, mid)
        return
    if data.startswith("rno:"):
        reject_receipt(chat_id, uid, data.split(":", 1)[1], cb_id)
        return
    if data.startswith("delplan:"):
        pid = data.split(":", 1)[1]
        with LOCK:
            STATE["plans"] = [p for p in STATE["plans"] if p["id"] != pid]
            save_state(STATE)
        answer_cb(cb_id, "پلن حذف شد")
        show_admin(chat_id, uid, mid)
        return
    answer_cb(cb_id)


# ────────────────────────────────── مسیریاب پیام ───────────────────────
def on_message(msg):
    text = msg.get("text", "") or ""
    if text.startswith("/start"):
        handle_start(msg)
        return
    if "photo" in msg:
        if handle_receipt_photo(msg):
            return
    # پیام‌های متنی مرحله‌ای
    if handle_admin_text(msg):
        return
    if handle_search_text(msg):
        return
    # پیش‌فرض: نمایش منو
    if text and not text.startswith("/"):
        show_home(msg["chat"]["id"], msg["from"]["id"])


# ───────────────────────────────────── حلقه‌ی long polling ────────────────
def set_commands():
    tg("setMyCommands", commands=[{"command": "start", "description": "🏠 منوی اصلی"}])


def main():
    if "اینجا" in BOT_TOKEN or BOT_TOKEN.count(":") == 0:
        print("\n⚠️  لطفاً ابتدا BOT_TOKEN و ADMIN_IDS را در بالای فایل (یا متغیرهای محیطی) تنظیم کنید.\n")
        return
    set_commands()
    me = tg("getMe").get("result", {})
    print(f"🤖 ربات {BRAND} فعال شد: @{me.get('username','?')}")
    offset = None
    while True:
        try:
            params = {"timeout": 50}
            if offset:
                params["offset"] = offset
            r = HTTP.get(f"{API}/getUpdates", params=params, timeout=60)
            data = r.json()
            if not data.get("ok"):
                time.sleep(2)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    if "message" in upd:
                        on_message(upd["message"])
                    elif "callback_query" in upd:
                        on_callback(upd["callback_query"])
                except Exception as e:
                    print("handler error:", e)
        except httpx.TimeoutException:
            continue
        except Exception as e:
            print("loop error:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()

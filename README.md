<div align="center">

# ⚡ Iliya Gateway

**پنل و ربات فروش کانفیگ — کاملاً اختصاصی با برند Iliya**

ساخته‌شده با FastAPI • WebSocket • Telegram Bot API

</div>

---

## 📦 اجزای پروژه

| فایل | توضیح |
|------|--------|
| `server.py` | سرور اصلی (گیت‌وی + داشبورد مدیریت + API ربات) |
| `ui.py` | قالب‌های HTML داشبورد، لاگین و صفحه‌ی عمومی کانفیگ |
| `bot.py` | ربات تلگرام فروش کانفیگ + پنل مدیریت |
| `requirements.txt` | وابستگی‌ها |
| `Procfile` | اجرای هم‌زمان سرور و ربات روی Railway |

---

## 🚀 راه‌اندازی

### ۱) نصب محلی
```bash
pip install -r requirements.txt
python server.py      # سرور روی پورت 8080
python bot.py         # ربات (در ترمینال جداگانه)
```

### ۲) دیپلوی روی Railway
1. این پوشه را در یک ریپازیتوری GitHub بگذارید.
2. در Railway پروژه را از همان ریپو بسازید.
3. دو سرویس بسازید: یکی با دستور `python server.py` و دیگری `python bot.py`.
4. متغیرهای محیطی زیر را تنظیم کنید.

---

## ⚙️ متغیرهای محیطی

### سرور (`server.py`)
| متغیر | پیش‌فرض | توضیح |
|-------|---------|--------|
| `ADMIN_PASSWORD` | `iliya` | رمز ورود به داشبورد |
| `BOT_API_KEY` | `iliya-secret-bridge` | کلید ارتباط ربات و سرور |
| `PORT` | `8080` | پورت |

### ربات (`bot.py`)
| متغیر | توضیح |
|-------|--------|
| `BOT_TOKEN` | توکن ربات از @BotFather |
| `ADMIN_IDS` | آیدی عددی مدیر (در بالای فایل) |
| `SERVER_URL` | آدرس سرور دیپلوی‌شده |
| `BOT_API_KEY` | باید دقیقاً با سرور یکی باشد |
| `CARD_NUMBER` / `CARD_HOLDER` | اطلاعات کارت برای شارژ |
| `SUPPORT_USERNAME` / `CHANNEL_USERNAME` | پشتیبانی و کانال |

> 💡 حداقل کاری که باید انجام دهید: `BOT_TOKEN` و `ADMIN_IDS` را در بالای `bot.py` پر کنید، و `SERVER_URL` را به آدرس سرور خود تغییر دهید.

---

## 🔐 امنیت
- حتماً `ADMIN_PASSWORD` و `BOT_API_KEY` پیش‌فرض را عوض کنید.
- فایل‌های `iliya_state.json` و `iliya_bot.json` داده‌ی زنده هستند و نباید در گیت قرار بگیرند.

---

<div align="center">ساخته‌شده با ❤️ برای <b>Iliya</b></div>

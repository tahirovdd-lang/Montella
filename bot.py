import asyncio
import logging
import json
import os
import time

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)

logging.basicConfig(level=logging.INFO)

# ====== НАСТРОЙКИ ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не найден. Добавь переменную окружения BOT_TOKEN.")

BOT_USERNAME = os.getenv("BOT_USERNAME", "montella_bot").replace("@", "").strip().lower()
ADMIN_ID = int(os.getenv("ADMIN_ID", "6013591658"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@MONTELLA_APP").strip()


def normalize_webapp_url(url: str) -> str:
    """
    Делает URL максимально стабильным для Telegram:
    - если это GitHub Pages папка, добавляет /index.html
    - сохраняет query ?v=...
    """
    url = (url or "").strip()
    if not url:
        return url

    if "?" in url:
        base, q = url.split("?", 1)
        q = "?" + q
    else:
        base, q = url, ""

    base = base.strip().rstrip("/")

    if "github.io" in base and not base.lower().endswith(".html"):
        base = base + "/index.html"

    return base + q


# ✅ ТВОЯ ССЫЛКА
DEFAULT_WEBAPP = "https://tahirovdd-lang.github.io/Montella/"
WEBAPP_URL = normalize_webapp_url(os.getenv("WEBAPP_URL", DEFAULT_WEBAPP))

logging.info(f"WEBAPP_URL (effective) = {WEBAPP_URL}")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ====== АНТИ-ДУБЛЬ START ======
_last_start: dict[int, float] = {}


def allow_start(user_id: int, ttl: float = 2.0) -> bool:
    now = time.time()
    prev = _last_start.get(user_id, 0.0)
    if now - prev < ttl:
        return False
    _last_start[user_id] = now
    return True


# ====== КНОПКИ ======
BTN_OPEN_MULTI = "Ochish • Открыть • Open"


def kb_webapp_reply() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_OPEN_MULTI, web_app=WebAppInfo(url=WEBAPP_URL))]
        ],
        resize_keyboard=True
    )


def kb_channel_url() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_OPEN_MULTI, url=WEBAPP_URL)]
        ]
    )


# ====== ТЕКСТ ======
def welcome_text() -> str:
    return (
        "🇷🇺 Добро пожаловать в <b>MONTELLA</b> 💧\n"
        "Откройте приложение — нажмите «Открыть» ниже.\n\n"
        "🇺🇿 <b>MONTELLA</b> 💧 ga xush kelibsiz!\n"
        "Ilovani ochish uchun pastdagi «Ochish» tugmasini bosing.\n\n"
        "🇬🇧 Welcome to <b>MONTELLA</b> 💧\n"
        "Tap “Open” below to launch the app."
    )


@dp.message(CommandStart())
async def start(message: types.Message):
    if not allow_start(message.from_user.id):
        return
    await message.answer(welcome_text(), reply_markup=kb_webapp_reply())


@dp.message(Command("startapp"))
async def startapp(message: types.Message):
    if not allow_start(message.from_user.id):
        return
    await message.answer(welcome_text(), reply_markup=kb_webapp_reply())


@dp.message(Command("debug_url"))
async def debug_url(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(f"WEBAPP_URL = <code>{WEBAPP_URL}</code>")


@dp.message(Command("post_shop"))
async def post_shop(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔️ Нет доступа.")

    text = (
        "🇷🇺 <b>MONTELLA</b> 💧\nНажмите кнопку ниже, чтобы открыть приложение.\n\n"
        "🇺🇿 <b>MONTELLA</b> 💧\nPastdagi tugma orqali ilovani oching.\n\n"
        "🇬🇧 <b>MONTELLA</b> 💧\nTap the button below to open the app."
    )

    try:
        sent = await bot.send_message(CHANNEL_ID, text, reply_markup=kb_channel_url())
        try:
            await bot.pin_chat_message(CHANNEL_ID, sent.message_id, disable_notification=True)
            await message.answer("✅ Пост отправлен в канал и закреплён.")
        except Exception:
            await message.answer(
                "✅ Пост отправлен в канал.\n"
                "⚠️ Не удалось закрепить — дай боту право «Закреплять сообщения»."
            )
    except Exception as e:
        logging.exception("CHANNEL POST ERROR")
        await message.answer(f"❌ Ошибка отправки в канал: <code>{e}</code>")


# ====== ВСПОМОГАТЕЛЬНЫЕ ======
def fmt_sum(n: int) -> str:
    try:
        n = int(n)
    except Exception:
        n = 0
    return f"{n:,}".replace(",", " ")


def tg_label(u: types.User) -> str:
    return f"@{u.username}" if u.username else u.full_name


def clean_str(v) -> str:
    return ("" if v is None else str(v)).strip()


def safe_int(v, default=0) -> int:
    try:
        if v is None or isinstance(v, bool):
            return default
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip().replace(" ", "")
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default


def parse_cart_items(data: dict) -> list[dict]:
    raw_items = data.get("items")
    if isinstance(raw_items, list):
        return raw_items

    raw_cart = data.get("cart")
    if isinstance(raw_cart, list):
        return raw_cart

    return []


def build_order_lines(data: dict) -> list[str]:
    raw_items = parse_cart_items(data)
    lines: list[str] = []

    for it in raw_items:
        if not isinstance(it, dict):
            continue

        name = clean_str(it.get("name")) or clean_str(it.get("id")) or "—"
        qty = safe_int(it.get("qty"), 0)
        if qty <= 0:
            continue

        price = safe_int(it.get("price"), 0)
        total = safe_int(it.get("total"), 0)

        if total <= 0 and price > 0:
            total = price * qty

        if total > 0:
            lines.append(f"• {name} × {qty} = {fmt_sum(total)} сум")
        elif price > 0:
            lines.append(f"• {name} × {qty} = {fmt_sum(price * qty)} сум")
        else:
            lines.append(f"• {name} × {qty}")

    return lines


def get_total_from_payload(data: dict) -> int:
    total = safe_int(data.get("total"), 0)
    if total > 0:
        return total

    cart_stats = data.get("cart_stats")
    if isinstance(cart_stats, dict):
        total = safe_int(cart_stats.get("sum"), 0)
        if total > 0:
            return total

    items = parse_cart_items(data)
    calc = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        item_total = safe_int(it.get("total"), 0)
        if item_total > 0:
            calc += item_total
        else:
            calc += safe_int(it.get("price"), 0) * safe_int(it.get("qty"), 0)
    return calc


def get_count_from_payload(data: dict) -> int:
    cart_stats = data.get("cart_stats")
    if isinstance(cart_stats, dict):
        count = safe_int(cart_stats.get("count"), 0)
        if count > 0:
            return count

    items = parse_cart_items(data)
    return sum(safe_int(it.get("qty"), 0) for it in items if isinstance(it, dict))


def is_consultation_payload(data: dict) -> bool:
    action = clean_str(data.get("action")).lower()
    text = clean_str(data.get("text"))
    items = parse_cart_items(data)

    if action in ("consultation", "consult", "message", "support"):
        return True

    if text and not items:
        return True

    return False


def is_order_payload(data: dict) -> bool:
    action = clean_str(data.get("action")).lower()
    items = parse_cart_items(data)

    if action == "order":
        return True

    if isinstance(items, list) and len(items) > 0:
        return True

    return False


# ====== ДАННЫЕ ИЗ WEBAPP ======
@dp.message(F.web_app_data)
async def webapp_data(message: types.Message):
    raw = message.web_app_data.data

    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    logging.info("WEBAPP DATA RAW: %s", raw)
    logging.info("WEBAPP DATA JSON: %s", data)

    if is_consultation_payload(data):
        text = clean_str(data.get("text"))
        phone = clean_str(data.get("phone"))

        if not text:
            return await message.answer("⚠️ Пустое сообщение. Напишите текст обращения.")

        admin_text = (
            "💬 <b>НОВОЕ ОБРАЩЕНИЕ MONTELLA</b>\n\n"
            f"📝 <b>Текст:</b> {text}\n"
        )

        if phone:
            admin_text += f"📞 <b>Телефон:</b> {phone}\n"

        admin_text += f"\n👤 <b>Telegram:</b> {tg_label(message.from_user)}"

        await bot.send_message(ADMIN_ID, admin_text)
        return await message.answer("✅ <b>Сообщение отправлено!</b>\nМы скоро ответим.")

    if is_order_payload(data):
        lines = build_order_lines(data)
        if not lines:
            return await message.answer("⚠️ Корзина пустая. Добавьте позиции и повторите.")

        total_sum = get_total_from_payload(data)
        total_count = get_count_from_payload(data)

        payment = clean_str(data.get("payment")) or "—"
        order_type = clean_str(data.get("type")) or "—"
        address = clean_str(data.get("address")) or "—"
        comment = clean_str(data.get("comment"))
        order_id = clean_str(data.get("order_id")) or "—"
        text = clean_str(data.get("text"))
        phone = clean_str(data.get("phone"))

        admin_text = (
            "🛒 <b>НОВАЯ ЗАЯВКА MONTELLA</b>\n"
            f"🆔 <b>{order_id}</b>\n\n"
            + "\n".join(lines) +
            f"\n\n📦 <b>Количество:</b> {total_count}"
            f"\n💰 <b>Сумма:</b> {fmt_sum(total_sum)} сум"
        )

        if order_type and order_type != "—":
            admin_text += f"\n🚚 <b>Тип:</b> {order_type}"
        if payment and payment != "—":
            admin_text += f"\n💳 <b>Оплата:</b> {payment}"
        if address and address != "—":
            admin_text += f"\n📍 <b>Адрес:</b> {address}"
        if phone:
            admin_text += f"\n📞 <b>Телефон:</b> {phone}"
        if text:
            admin_text += f"\n💬 <b>Сообщение:</b> {text}"

        admin_text += f"\n👤 <b>Telegram:</b> {tg_label(message.from_user)}"

        if comment:
            admin_text += f"\n🗒 <b>Комментарий:</b> {comment}"

        await bot.send_message(ADMIN_ID, admin_text)
        return await message.answer("✅ <b>Заявка отправлена!</b>\nМы скоро свяжемся с вами.")

    await message.answer("⚠️ Данные не распознаны. Откройте приложение и попробуйте снова.")


# ====== ЗАПУСК ======
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

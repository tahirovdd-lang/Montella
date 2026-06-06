import asyncio
import logging
import os
import html
import json
import re
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.exceptions import TelegramConflictError, TelegramNetworkError

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

BOT_TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("API_TOKEN")
    or os.getenv("BOT_API_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TOKEN")
)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден")

ADMIN_ID = int(os.getenv("ADMIN_ID", "6013591658"))
PORT = int(os.getenv("PORT", "3000"))

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://tahirovdd-lang.github.io/Montella/").strip()
if WEBAPP_URL.endswith("/"):
    WEBAPP_URL += "index.html"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


def keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ochish • Открыть", web_app=WebAppInfo(url=WEBAPP_URL))]
        ],
        resize_keyboard=True
    )


def welcome_text():
    return (
        "🇷🇺 <b>Добро пожаловать в MONTELLA 💧</b>\n\n"
        "Нажмите кнопку <b>«Открыть»</b> ниже, чтобы перейти в приложение.\n"
        "В приложении вы сможете ознакомиться с продукцией, оформить заказ и связаться с нами.\n\n"
        "🇺🇿 <b>MONTELLA 💧 ga xush kelibsiz!</b>\n\n"
        "Ilovaga kirish uchun quyidagi <b>«Ochish»</b> tugmasini bosing.\n"
        "Ilova orqali mahsulotlar bilan tanishishingiz, buyurtma berishingiz va biz bilan bog‘lanishingiz mumkin."
    )


def clean_str(value):
    if value is None:
        return ""
    return str(value).strip()


def esc(value):
    return html.escape(clean_str(value))


def fmt_sum(value):
    try:
        value = int(float(str(value).replace(" ", "")))
    except Exception:
        value = 0
    return f"{value:,}".replace(",", " ")


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(float(str(value).replace(" ", "")))
    except Exception:
        return default


def normalize_phone(phone):
    digits = re.sub(r"\D", "", clean_str(phone))

    if digits.startswith("998") and len(digits) == 12:
        return "+" + digits

    if len(digits) == 9:
        return "+998" + digits

    if digits.startswith("8") and len(digits) == 10:
        return "+998" + digits[1:]

    if clean_str(phone).startswith("+998"):
        return clean_str(phone)

    return clean_str(phone)


def valid_uz_phone(phone):
    digits = re.sub(r"\D", "", normalize_phone(phone))
    return digits.startswith("998") and len(digits) == 12


def tg_user_label(user):
    if user.username:
        return f"@{user.username}"
    return user.full_name or "Пользователь"


def get_items(data):
    if isinstance(data.get("items"), list):
        return data.get("items")
    if isinstance(data.get("cart"), list):
        return data.get("cart")
    if isinstance(data.get("products"), list):
        return data.get("products")
    return []


def build_order_lines(data):
    lines = []
    items = get_items(data)

    for item in items:
        if not isinstance(item, dict):
            continue

        name = clean_str(item.get("name") or item.get("title") or item.get("id") or "Товар")
        qty = safe_int(item.get("qty") or item.get("quantity") or item.get("count"), 0)
        price = safe_int(item.get("price"), 0)
        total = safe_int(item.get("total") or item.get("sum"), 0)

        if qty <= 0:
            qty = 1

        if total <= 0 and price > 0:
            total = price * qty

        if total > 0:
            lines.append(f"• {esc(name)} × {qty} = {fmt_sum(total)} сум")
        else:
            lines.append(f"• {esc(name)} × {qty}")

    return lines


def get_total(data):
    for key in ("total", "total_sum", "sum", "amount"):
        total = safe_int(data.get(key), 0)
        if total > 0:
            return total

    total = 0
    for item in get_items(data):
        if not isinstance(item, dict):
            continue

        item_total = safe_int(item.get("total") or item.get("sum"), 0)
        if item_total > 0:
            total += item_total
        else:
            qty = safe_int(item.get("qty") or item.get("quantity") or item.get("count"), 1)
            price = safe_int(item.get("price"), 0)
            total += price * qty

    return total


def is_order_payload(data):
    action = clean_str(data.get("action")).lower()
    return (
        action in ("order", "checkout", "checkout_order", "cart_order")
        or len(get_items(data)) > 0
    )


@dp.message(CommandStart())
async def start(message: types.Message):
    logging.info("START from %s", message.from_user.id)
    await message.answer(
        welcome_text(),
        reply_markup=keyboard()
    )


@dp.message(Command("ping"))
async def ping(message: types.Message):
    logging.info("PING from %s", message.from_user.id)
    await message.answer("✅ PING OK")


@dp.message(Command("debug"))
async def debug(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    me = await bot.get_me()
    await message.answer(
        f"✅ Код запущен\n"
        f"Бот: @{html.escape(me.username or '')}\n"
        f"ID: <code>{me.id}</code>\n"
        f"WEBAPP_URL: <code>{html.escape(WEBAPP_URL)}</code>\n"
        f"PORT: <code>{PORT}</code>"
    )


@dp.message(F.web_app_data)
async def webapp_data(message: types.Message):
    raw = message.web_app_data.data
    logging.info("WEBAPP RAW DATA: %s", raw)

    try:
        data = json.loads(raw)
    except Exception:
        logging.exception("JSON parse error")
        await message.answer("❌ Ошибка данных заказа. Попробуйте оформить заказ ещё раз.")
        return

    if not is_order_payload(data):
        await message.answer("⚠️ Данные не распознаны как заказ. Откройте приложение и попробуйте снова.")
        return

    address = clean_str(
        data.get("address")
        or data.get("delivery_address")
        or data.get("deliveryAddress")
    )

    phone = normalize_phone(
        data.get("phone")
        or data.get("telephone")
        or data.get("client_phone")
        or data.get("clientPhone")
    )

    if not valid_uz_phone(phone):
        await message.answer(
            "⚠️ Укажите правильный номер телефона.\n\n"
            "Формат: <b>+998 XX XXX XX XX</b>"
        )
        return

    if not address:
        await message.answer(
            "⚠️ Укажите адрес доставки.\n\n"
            "Без адреса доставки заказ не принимается."
        )
        return

    order_lines = build_order_lines(data)
    if not order_lines:
        await message.answer("⚠️ Корзина пустая. Добавьте товары и повторите заказ.")
        return

    total = get_total(data)
    user_label = tg_user_label(message.from_user)

    admin_text = (
        "🛒 <b>НОВЫЙ ЗАКАЗ MONTELLA</b>\n\n"
        f"👤 <b>Telegram:</b> {html.escape(user_label)}\n"
        f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n"
        f"📞 <b>Телефон:</b> {html.escape(phone)}\n"
        f"📍 <b>Адрес доставки:</b> {html.escape(address)}\n\n"
        f"📦 <b>Заказ:</b>\n"
        + "\n".join(order_lines) +
        f"\n\n💰 <b>Сумма:</b> {fmt_sum(total)} сум"
    )

    comment = clean_str(data.get("comment"))
    if comment:
        admin_text += f"\n📝 <b>Комментарий:</b> {html.escape(comment)}"

    try:
        await bot.send_message(ADMIN_ID, admin_text)
        await message.answer(
            "✅ <b>Заказ принят!</b>\n\n"
            "Мы скоро свяжемся с вами.",
            reply_markup=keyboard()
        )
    except Exception as e:
        logging.exception("ORDER SEND ERROR")
        await message.answer(
            f"❌ Ошибка отправки заказа админу:\n<code>{html.escape(str(e))}</code>"
        )


@dp.message()
async def any_message(message: types.Message):
    await message.answer(
        welcome_text(),
        reply_markup=keyboard()
    )


async def health(request):
    return web.Response(text="OK")


async def run_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logging.info("Health web server started on port %s", PORT)


async def run_bot():
    while True:
        try:
            logging.info("Starting polling...")

            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                polling_timeout=10
            )

        except TelegramConflictError:
            logging.error("Запущена вторая копия этого же бота. Останови старый контейнер.")
            await asyncio.sleep(15)

        except TelegramNetworkError:
            logging.exception("Ошибка сети Telegram. Перезапуск через 10 секунд.")
            await asyncio.sleep(10)

        except Exception:
            logging.exception("Бот упал. Перезапуск через 10 секунд.")
            await asyncio.sleep(10)


async def main():
    await run_web_server()
    await run_bot()


if __name__ == "__main__":
    asyncio.run(main())

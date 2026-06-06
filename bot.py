import asyncio
import logging
import os
import html
from aiohttp import web

from aiogram import Bot, Dispatcher, types
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
            [KeyboardButton(text="Ochish • Открыть • Open", web_app=WebAppInfo(url=WEBAPP_URL))]
        ],
        resize_keyboard=True
    )


@dp.message(CommandStart())
async def start(message: types.Message):
    logging.info("START from %s", message.from_user.id)
    await message.answer(
        "✅ Бот работает.\n\nНажмите кнопку ниже, чтобы открыть приложение.",
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


@dp.message()
async def any_message(message: types.Message):
    await message.answer(
        "✅ Бот получил сообщение.\nНажмите кнопку ниже.",
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

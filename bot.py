import asyncio
import logging
import os
import html

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.exceptions import TelegramConflictError, TelegramNetworkError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("API_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN/API_TOKEN не найден")

ADMIN_ID = int(os.getenv("ADMIN_ID", "6013591658"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://tahirovdd-lang.github.io/Montella/").strip()

if WEBAPP_URL.endswith("/"):
    WEBAPP_URL += "index.html"

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)

dp = Dispatcher()


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))]
        ],
        resize_keyboard=True
    )


@dp.message(CommandStart())
async def start(message: types.Message):
    logging.info("START received from %s", message.from_user.id)

    await message.answer(
        "✅ Бот работает.\n\n"
        "Нажмите кнопку ниже, чтобы открыть приложение.",
        reply_markup=main_keyboard()
    )


@dp.message(Command("ping"))
async def ping(message: types.Message):
    await message.answer("✅ PING OK")


@dp.message(Command("debug"))
async def debug(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    me = await bot.get_me()
    await message.answer(
        f"✅ Бот запущен\n"
        f"Username: @{html.escape(me.username or '')}\n"
        f"ID: <code>{me.id}</code>\n"
        f"WEBAPP_URL: <code>{html.escape(WEBAPP_URL)}</code>"
    )


async def startup_notify():
    try:
        me = await bot.get_me()
        await bot.send_message(
            ADMIN_ID,
            f"✅ Бот запустился\n"
            f"Username: @{html.escape(me.username or '')}\n"
            f"ID: <code>{me.id}</code>\n"
            f"WEBAPP_URL: <code>{html.escape(WEBAPP_URL)}</code>"
        )
    except Exception:
        logging.exception("Не удалось отправить сообщение админу при запуске")


async def main():
    while True:
        try:
            logging.info("Deleting webhook...")
            await bot.delete_webhook(drop_pending_updates=True)

            await startup_notify()

            logging.info("Starting polling...")
            await dp.start_polling(bot)

        except TelegramConflictError:
            logging.error("❌ Запущена вторая копия этого же бота. Останови старый хостинг/контейнер.")
            await asyncio.sleep(10)

        except TelegramNetworkError:
            logging.exception("Ошибка сети Telegram. Перезапуск через 10 секунд.")
            await asyncio.sleep(10)

        except Exception:
            logging.exception("Бот упал. Перезапуск через 10 секунд.")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())

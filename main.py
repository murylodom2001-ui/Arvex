import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import FSInputFile

import database as db
from handle.routes import router, PRODUCTS, get_path

# Загружаем переменные из .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("ОШИБКА: BOT_TOKEN не указан в файле .env!")

# Инициализируем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Подключаем роутер с интерфейсом магазина
dp.include_router(router)


# --------------------------------------------------
# ОБРАБОТЧИК ВЕБХУКА ОТ XROCKET
# --------------------------------------------------
async def xrocket_webhook_handler(request: web.Request) -> web.Response:
    """
    Принимает POST-уведомление от xRocket при успешной оплате счёта.
    Сверяет order_id, переводит заказ в статус 'paid' и выдаёт ZIP-архив.
    """
    try:
        payload = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    # Проверяем тип события от xRocket
    if payload.get("type") == "invoice_paid":
        invoice_data = payload.get("data", {})
        hidden_data = invoice_data.get("hiddenData")

        if hidden_data:
            try:
                order_id = int(hidden_data)
            except ValueError:
                return web.Response(status=200, text="OK")

            # Фиксируем оплату в базе данных с защитой от повторной выдачи
            order = await db.mark_order_paid(order_id)

            if order:
                user_id = order["user_id"]
                product_id = order["product_id"]
                product = PRODUCTS.get(product_id)
                product_title = product["title"] if product else product_id

                # 1. Отправляем покупателю уведомление об успешной оплате
                success_text = (
                    f"✅ <b>Оплата заказа #{order_id} успешно получена!</b>\n\n"
                    f"📦 <b>Товар:</b> {product_title}\n"
                    f"Благодарим за выбор <b>NEXORA DIGITAL</b>!\n\n"
                    f"Файл готов к скачиванию и отправлен ниже 👇"
                )
                await bot.send_message(
                    chat_id=user_id,
                    text=success_text,
                    parse_mode="HTML"
                )

                # 2. Отправляем цифровой товар (ZIP-архив)
                if product and "file" in product:
                    file_path = get_path(product["file"])
                    if file_path.exists():
                        doc = FSInputFile(file_path)
                        await bot.send_document(
                            chat_id=user_id,
                            document=doc,
                            caption=f"📦 {product_title} — готово к использованию!"
                        )
                    else:
                        await bot.send_message(
                            chat_id=user_id,
                            text="⚠️ Файл формируется. Напишите менеджеру: @arvex_ar"
                        )

    # xRocket требует ответ 200 OK
    return web.Response(status=200, text="OK")


# --------------------------------------------------
# ЗАПУСК ФОНОВОГО ВЕБ-СЕРВЕРА ДЛЯ ВЕБХУКОВ
# --------------------------------------------------
async def start_web_server():
    app = web.Application()
    app.router.add_post("/webhook", xrocket_webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("🌐 Вебхук-сервер xRocket слушает порт 8080 (путь: /webhook)")


# --------------------------------------------------
# ТОЧКА ВХОДА: СТАРТ ВСЕЙ СИСТЕМЫ
# --------------------------------------------------
async def main():
    # 1. Инициализируем таблицы в базе данных nexora.db
    await db.init_db()
    print("💾 База данных nexora.db подключена!")

    # 2. Запускаем сервер приёма оплат
    await start_web_server()

    # 3. Запускаем Telegram-бота
    print("🚀 Бот Nexora Digital успешно запущен в режиме polling!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

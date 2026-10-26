import os
from pathlib import Path
import aiohttp
from dotenv import load_dotenv

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    InputMediaPhoto,
)

import database as db

load_dotenv()

router = Router()

BASE_DIR = Path(__file__).resolve().parent.parent

# Токен xRocket для генерации счетов
XROCKET_API_KEY = os.getenv("XROCKET_API_KEY", "")
XROCKET_URL = "https://pay.ton-rocket.com/tg-invoices"

# Кэш file_id изображений
PHOTO_CACHE: dict[str, str] = {}

# Каталог товаров с привязкой цен и файлов
PRODUCTS = {
    "tgbot": {
        "title": "🤖 TG BOT TEMPLATE",
        "short_title": "TG Bot Template",
        "price": "40 ₽",
        "usdt": 0.5,
        "image": "description/shablon_tgbot.jpg",
        "file": "tovar/NEXORA_DIGITAL_STARTER_PACK.zip",
        "desc": (
            "🤖 <b>SHABLON TG BOT</b>\n\n"
            "Готовая база для Telegram-бота на Python (aiogram 3).\n\n"
            "📦 <b>В комплекте:</b>\n"
            "• Чистая модульная архитектура\n"
            "• Настроенный роутинг и клавиатуры\n"
            "• Конфигурация через .env\n\n"
            "💰 <b>Цена:</b> <code>299 ₽</code>\n"
            "💵 <b>3.7 USDT</b>"
        )
    },
    "site": {
        "title": "🌐 САЙТ-ПОРТФОЛИО",
        "short_title": "Сайт-портфолио",
        "price": "299 ₽",
        "usdt": 2.5,
        "image": "description/sait_shablon.jpg",
        "file": "tovar/NEXORA_SITE_PORTFOLIO_TEMPLATE.zip",
        "desc": (
            "🌐 <b>САЙТ-ПОРТФОЛИО</b>\n\n"
            "Современный адаптивный веб-шаблон для фрилансеров.\n\n"
            "📦 <b>В комплекте:</b>\n"
            "• Стек HTML5, CSS3, JavaScript\n"
            "• Блоки «О себе», «Кейсы», «Контакты»\n"
            "• Адаптив под мобильные и ПК\n\n"
            "💰 <b>Цена:</b> <code>299 ₽</code>\n"
            "💵 <b>2.5 USDT</b>"
        )
    },
    "avto": {
        "title": "🐍 PYTHON AUTOMATION",
        "short_title": "Python Automation",
        "price": "249 ₽",
        "usdt": 3.1,
        "image": "description/avtomat.jpg",
        "file": "tovar/NEXORA_PYTHON_AUTOMATION_PACK.zip",
        "desc": (
            "🐍 <b>PYTHON AUTOMATION PACK</b>\n\n"
            "Скрипты для избавления от повседневной рутины.\n\n"
            "📦 <b>В комплекте:</b>\n"
            "• File Organizer — сортировка файлов\n"
            "• Batch Renamer — переименование пачками\n"
            "• CSV Cleaner — очистка таблиц\n\n"
            "💰 <b>Цена:</b> <code>249 ₽</code>\n"
            "💵 <b>3.1 USDT</b>"
        )
    },
    "html": {
        "title": "🎨 NEXORA UI KIT",
        "short_title": "NEXORA UI Kit",
        "price": "349 ₽",
        "usdt": 4.5,
        "image": "description/html.jpg",
        "file": "tovar/NEXORA_UI_KIT.zip",
        "desc": (
            "🎨 <b>NEXORA UI KIT</b>\n\n"
            "Комплект готовых веб-компонентов для интерфейсов.\n\n"
            "📦 <b>В комплекте:</b>\n"
            "• Карточки, кнопки, формы, таблицы\n"
            "• Светлая и тёмная темы\n"
            "• Полная адаптивность сетки\n\n"
            "💰 <b>Цена:</b> <code>349 ₽</code>\n"
            "💵 <b>4.5 USDT</b>"
        )
    },
}


def get_path(relative_path: str) -> Path:
    return BASE_DIR / relative_path


def shorten(text: str, limit: int = 1000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - 3].rsplit(" ", 1)[0] + "..."


async def create_xrocket_invoice(amount: float, order_id: int, product_title: str) -> str:
    """Запрашивает персональный счёт у xRocket API."""
    headers = {
        "Rocket-Pay-Key": XROCKET_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "amount": amount,
        "currency": "USDT",
        "description": f"Заказ #{order_id} | {product_title}",
        "hiddenData": str(order_id),
        "numPayments": 1
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(XROCKET_URL, json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("success"):
                return data["data"]["link"]
            raise Exception(data.get("message") or str(data))


# --------------------------------------------------
# КЛАВИАТУРЫ
# --------------------------------------------------

def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛍 Каталог товаров",
                    callback_data="catalog",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ О нас",
                    callback_data="about",
                ),
                InlineKeyboardButton(
                    text="🎧 Поддержка",
                    callback_data="support",
                ),
            ],
        ]
    )


def catalog_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{PRODUCTS['tgbot']['short_title']} — {PRODUCTS['tgbot']['price']}",
                    callback_data="product:tgbot",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{PRODUCTS['site']['short_title']} — {PRODUCTS['site']['price']}",
                    callback_data="product:site",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{PRODUCTS['avto']['short_title']} — {PRODUCTS['avto']['price']}",
                    callback_data="product:avto",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{PRODUCTS['html']['short_title']} — {PRODUCTS['html']['price']}",
                    callback_data="product:html",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Главное меню",
                    callback_data="home",
                ),
            ],
        ]
    )


def product_keyboard(product_id: str) -> InlineKeyboardMarkup:
    prod = PRODUCTS.get(product_id, {})
    price = prod.get("price", "")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🟢 Купить — {price}",
                    callback_data=f"buy:{product_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ В каталог",
                    callback_data="catalog",
                ),
                InlineKeyboardButton(
                    text="🏠 В меню",
                    callback_data="home",
                ),
            ],
        ]
    )


def buy_keyboard(product_id: str) -> InlineKeyboardMarkup:
    prod = PRODUCTS.get(product_id, {})
    price = prod.get("price", "")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🟢 Оплатить чек ({price})",
                    callback_data=f"pay:{product_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ К товару",
                    callback_data=f"product:{product_id}",
                ),
                InlineKeyboardButton(
                    text="🛍 В каталог",
                    callback_data="catalog",
                ),
            ],
        ]
    )


def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Написать в поддержку",
                    url="https://t.me/arvex_ar",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ В главное меню",
                    callback_data="home",
                ),
            ],
        ]
    )


def about_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛍 Перейти в каталог",
                    callback_data="catalog",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ В главное меню",
                    callback_data="home",
                ),
            ],
        ]
    )


async def edit_screen(
    callback: CallbackQuery,
    image_path: str,
    caption: str,
    keyboard: InlineKeyboardMarkup,
):
    await callback.answer()

    cached_file_id = PHOTO_CACHE.get(image_path)
    photo_input = cached_file_id if cached_file_id else FSInputFile(get_path(image_path))

    try:
        edited_msg = await callback.message.edit_media(
            media=InputMediaPhoto(
                media=photo_input,
                caption=shorten(caption),
                parse_mode="HTML",
            ),
            reply_markup=keyboard,
        )

        if not cached_file_id and edited_msg.photo:
            PHOTO_CACHE[image_path] = edited_msg.photo[-1].file_id

    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise e


# --------------------------------------------------
# ХЭНДЛЕРЫ НАВИГАЦИИ
# --------------------------------------------------

HOME_CAPTION = (
    "⚡️ <b>NEXORA DIGITAL</b>\n\n"
    "Магазин готовых цифровых инструментов для разработчиков.\n"
    "Шаблоны сайтов, боты, скрипты и UI-компоненты.\n\n"
    "🚀 <i>Мгновенная выдача файлов сразу после оплаты!</i>"
)


@router.message(Command("start"))
async def start_handler(message: Message):
    # Регистрируем пользователя в базе
    await db.add_user(message.from_user.id, message.from_user.username)

    image_path = "images/Банер.jpg"
    cached_file_id = PHOTO_CACHE.get(image_path)
    photo_input = cached_file_id if cached_file_id else FSInputFile(get_path(image_path))

    msg = await message.answer_photo(
        photo=photo_input,
        caption=shorten(HOME_CAPTION),
        reply_markup=home_keyboard(),
        parse_mode="HTML",
    )

    if not cached_file_id and msg.photo:
        PHOTO_CACHE[image_path] = msg.photo[-1].file_id


@router.callback_query(F.data == "home")
async def home_callback_handler(callback: CallbackQuery):
    await edit_screen(
        callback=callback,
        image_path="images/Банер.jpg",
        caption=HOME_CAPTION,
        keyboard=home_keyboard(),
    )


CATALOG_CAPTION = (
    "🛍 <b>КАТАЛОГ ЦИФРОВЫХ ТОВАРОВ</b>\n\n"
    "Выберите продукт, чтобы посмотреть подробности и оформить заказ:"
)


@router.message(Command("tovar"))
async def tovar_command_handler(message: Message):
    image_path = "images/товары.jpg"
    cached_file_id = PHOTO_CACHE.get(image_path)
    photo_input = cached_file_id if cached_file_id else FSInputFile(get_path(image_path))

    msg = await message.answer_photo(
        photo=photo_input,
        caption=shorten(CATALOG_CAPTION),
        reply_markup=catalog_keyboard(),
        parse_mode="HTML",
    )

    if not cached_file_id and msg.photo:
        PHOTO_CACHE[image_path] = msg.photo[-1].file_id


@router.callback_query(F.data == "catalog")
async def catalog_callback_handler(callback: CallbackQuery):
    await edit_screen(
        callback=callback,
        image_path="images/товары.jpg",
        caption=CATALOG_CAPTION,
        keyboard=catalog_keyboard(),
    )


@router.callback_query(F.data.startswith("product:"))
async def product_callback_handler(callback: CallbackQuery):
    product_id = callback.data.split(":", 1)[1]
    product = PRODUCTS.get(product_id)

    if not product:
        await callback.answer("⚠️ Товар не найден.", show_alert=True)
        return

    await edit_screen(
        callback=callback,
        image_path=product["image"],
        caption=product["desc"],
        keyboard=product_keyboard(product_id),
    )


@router.callback_query(F.data.startswith("buy:"))
async def buy_callback_handler(callback: CallbackQuery):
    product_id = callback.data.split(":", 1)[1]
    product = PRODUCTS.get(product_id)

    if not product:
        await callback.answer("⚠️ Товар не найден.", show_alert=True)
        return

    caption = (
        f"💳 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\n"
        f"📦 <b>Товар:</b> {product['title']}\n"
        f"💰 <b>К оплате:</b> <code>{product['price']}</code> ({product['usdt']} USDT)\n\n"
        f"⚡️ Нажмите кнопку ниже для перехода к оплате."
    )

    await edit_screen(
        callback=callback,
        image_path=product["image"],
        caption=caption,
        keyboard=buy_keyboard(product_id),
    )


# --------------------------------------------------
# ВЫСТАВЛЕНИЕ СЧЁТА XROCKET
# --------------------------------------------------

@router.callback_query(F.data.startswith("pay:"))
async def pay_callback_handler(callback: CallbackQuery):
    product_id = callback.data.split(":", 1)[1]
    product = PRODUCTS.get(product_id)

    if not product:
        await callback.answer("⚠️ Товар не найден.", show_alert=True)
        return

    if not XROCKET_API_KEY:
        await callback.answer("⚠️ Ошибка: XROCKET_API_KEY не указан в .env", show_alert=True)
        return

    await callback.answer("⏳ Создаём счёт в xRocket...", show_alert=False)

    # 1. Запись заказа в базу данных со статусом 'pending'
    order_id = await db.create_order(
        user_id=callback.from_user.id,
        product_id=product_id,
        amount_rub=product["price"],
        amount_usdt=product["usdt"]
    )

    # 2. Запрос ссылки на оплату в xRocket
    try:
        invoice_link = await create_xrocket_invoice(
            amount=product["usdt"],
            order_id=order_id,
            product_title=product["title"]
        )

        pay_keyboard_link = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"💸 Оплатить {product['usdt']} USDT в @xrocket",
                        url=invoice_link,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="◀️ Назад к товару",
                        callback_data=f"product:{product_id}",
                    )
                ]
            ]
        )

        caption = (
            f"🧾 <b>СЧЁТ НА ОПЛАТУ #{order_id}</b>\n\n"
            f"📦 <b>Товар:</b> {product['title']}\n"
            f"💰 <b>Сумма:</b> <code>{product['price']}</code> ({product['usdt']} USDT)\n\n"
            f"👇 Нажмите кнопку ниже для оплаты в боте xRocket.\n"
            f"<i>После подтверждения оплаты архив автоматически поступит в этот чат!</i>"
        )

        await edit_screen(
            callback=callback,
            image_path=product["image"],
            caption=caption,
            keyboard=pay_keyboard_link,
        )
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка создания счёта xRocket: {e}")


@router.callback_query(F.data == "about")
async def about_callback_handler(callback: CallbackQuery):
    about_caption = (
        "ℹ️ <b>О ПРОЕКТЕ NEXORA DIGITAL</b>\n\n"
        "Мы создаем проверенные цифровые инструменты для разработчиков и дизайнеров.\n\n"
        "• <b>Качество:</b> чистый код и понятная документация\n"
        "• <b>Скорость:</b> мгновенная выдача файлов после оплаты\n"
        "• <b>Безопасность:</b> прямые криптоплатежи без посредников"
    )
    await edit_screen(
        callback=callback,
        image_path="images/о нас.jpg",
        caption=about_caption,
        keyboard=about_keyboard(),
    )


@router.message(Command("support"))
async def support_command_handler(message: Message):
    image_path = "images/support.jpg"
    cached_file_id = PHOTO_CACHE.get(image_path)
    photo_input = cached_file_id if cached_file_id else FSInputFile(get_path(image_path))

    support_caption = (
        "🎧 <b>СЛУЖБА ПОДДЕРЖКИ</b>\n\n"
        "Возникли вопросы по товару, оплате или распаковке архива?\n\n"
        "⚡️ <b>Время ответа:</b> 5–15 минут\n"
        "👤 <b>Специалист:</b> @arvex_ar"
    )

    msg = await message.answer_photo(
        photo=photo_input,
        caption=shorten(support_caption),
        reply_markup=support_keyboard(),
        parse_mode="HTML",
    )

    if not cached_file_id and msg.photo:
        PHOTO_CACHE[image_path] = msg.photo[-1].file_id


@router.callback_query(F.data == "support")
async def support_callback_handler(callback: CallbackQuery):
    support_caption = (
        "🎧 <b>СЛУЖБА ПОДДЕРЖКИ</b>\n\n"
        "Возникли вопросы по товару, оплате или распаковке архива?\n\n"
        "⚡️ <b>Время ответа:</b> 5–15 минут\n"
        "👤 <b>Специалист:</b> @arvex_ar"
    )
    await edit_screen(
        callback=callback,
        image_path="images/support.jpg",
        caption=support_caption,
        keyboard=support_keyboard(),
    )

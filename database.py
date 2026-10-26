import aiosqlite
from pathlib import Path
from typing import Optional, Dict, Any, List

# Путь к файлу базы данных в корне проекта
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "nexora.db"


async def init_db() -> None:
    """
    Создаёт таблицы в базе данных при первом запуске,
    если они ещё не созданы.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Таблица пользователей
        # Хранит Telegram ID, никнейм и дату первого запуска бота
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Таблица заказов
        # Хранит каждый сформированный чек, его сумму и статус (pending / paid)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                amount_rub TEXT,
                amount_usdt REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        # Создаем индекс для быстрого поиска заказов пользователя
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_user_status 
            ON orders (user_id, status)
        """)

        await db.commit()


async def add_user(user_id: int, username: Optional[str] = None) -> None:
    """
    Регистрирует нового пользователя или обновляет никнейм,
    если пользователь сменил его в Telegram.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username
        """, (user_id, username or "Без username"))
        await db.commit()


async def create_order(
        user_id: int,
        product_id: str,
        amount_rub: str,
        amount_usdt: float
) -> int:
    """
    Фиксирует намерение покупки и создаёт заказ со статусом 'pending'.
    Возвращает уникальный order_id (номер заказа для чека xRocket).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO orders (user_id, product_id, amount_rub, amount_usdt, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (user_id, product_id, amount_rub, amount_usdt))
        await db.commit()
        return cursor.lastrowid


async def get_order(order_id: int) -> Optional[Dict[str, Any]]:
    """
    Находит заказ по его номеру и возвращает словарь с его полями.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM orders WHERE order_id = ?
        """, (order_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def mark_order_paid(order_id: int) -> Optional[Dict[str, Any]]:
    """
    Переводит заказ в статус 'paid' (оплачен) и проставляет время оплаты.

    Защита от двойной выдачи:
    Если заказ уже был оплачен ранее, вернёт None.
    Если оплата зафиксирована впервые — вернёт данные заказа (user_id, product_id).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Проверяем текущее состояние заказа
        async with db.execute("""
            SELECT user_id, product_id, status FROM orders WHERE order_id = ?
        """, (order_id,)) as cursor:
            order = await cursor.fetchone()
            if not order or order["status"] == "paid":
                return None

        # Меняем статус на paid и сохраняем точное время
        await db.execute("""
            UPDATE orders 
            SET status = 'paid', paid_at = CURRENT_TIMESTAMP 
            WHERE order_id = ?
        """, (order_id,))
        await db.commit()

        return dict(order)


async def get_user_paid_products(user_id: int) -> List[str]:
    """
    Возвращает список всех ключей товаров (product_id),
    которые пользователь когда-либо успешно приобрёл.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT DISTINCT product_id 
            FROM orders 
            WHERE user_id = ? AND status = 'paid'
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

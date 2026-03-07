# src/utils/database.py
import sqlite3
from utils.platform_config import get_config

CFG = get_config()
DB_PATH = str(CFG.PATHS.DB_PATH)


def get_connection():
    return sqlite3.connect(DB_PATH)


def _get_columns(cur) -> set[str]:
    cur.execute("PRAGMA table_info(users)")
    return {row[1] for row in cur.fetchall()}


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    # ---- migration: add missing columns safely ----
    columns = _get_columns(cursor)

    needed = {
        "age": "INTEGER DEFAULT 0",
        "gender": "TEXT DEFAULT ''",
        "game1_score": "INTEGER DEFAULT 0",
        "game1_total": "INTEGER DEFAULT 5",
        "game2_s1": "INTEGER DEFAULT 0",
        "game2_s2": "INTEGER DEFAULT 0",
        "game2_s3": "INTEGER DEFAULT 0",
        "game2_s4": "INTEGER DEFAULT 0",
        "game2_s5": "INTEGER DEFAULT 0",
        "game2_avg": "INTEGER DEFAULT 0",
        "game3_s1": "INTEGER DEFAULT 0",
        "game3_s2": "INTEGER DEFAULT 0",
        "game3_avg": "INTEGER DEFAULT 0",
    }

    for col, sql_type in needed.items():
        if col not in columns:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {sql_type}")

    conn.commit()
    conn.close()


def get_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM users ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_user_details(user_id: int) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            COALESCE(name, ''),
            COALESCE(age, 0),
            COALESCE(gender, ''),
            COALESCE(game1_score, 0),
            COALESCE(game1_total, 5),
            COALESCE(game2_avg, 0),
            COALESCE(game3_avg, 0)
        FROM users
        WHERE id = ?
    """, (int(user_id),))

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": int(row[0]),
        "name": str(row[1] or ""),
        "age": int(row[2] or 0),
        "gender": str(row[3] or ""),
        "game1_score": int(row[4] or 0),
        "game1_total": int(row[5] or 5),
        "game2_avg": int(row[6] or 0),
        "game3_avg": int(row[7] or 0),
    }


def add_user(name: str, age: int = 0, gender: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, age, gender) VALUES (?, ?, ?)",
            (name.strip(), int(age), gender.strip())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()


def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def add_game1_score(user_id: int, score: int, total: int):
    conn = get_connection()
    cur = conn.cursor()

    columns = _get_columns(cur)

    if "game1_score" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN game1_score INTEGER DEFAULT 0")

    if "game1_total" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN game1_total INTEGER DEFAULT 5")

    cur.execute("""
        UPDATE users
        SET game1_score = ?, game1_total = ?
        WHERE id = ?
    """, (score, total, user_id))

    conn.commit()
    conn.close()


def add_game2_scores(user_id: int, scores: list[int]):
    if len(scores) != 5:
        raise ValueError("Game2 requires exactly 5 scores")

    conn = get_connection()
    cur = conn.cursor()

    columns = _get_columns(cur)

    needed = [
        ("game2_s1", 0),
        ("game2_s2", 0),
        ("game2_s3", 0),
        ("game2_s4", 0),
        ("game2_s5", 0),
        ("game2_avg", 0),
    ]

    for col, default in needed:
        if col not in columns:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT {default}")

    avg = int(round(sum(scores) / 5))

    cur.execute("""
        UPDATE users
        SET game2_s1=?, game2_s2=?, game2_s3=?, game2_s4=?, game2_s5=?, game2_avg=?
        WHERE id=?
    """, (
        int(scores[0]), int(scores[1]), int(scores[2]),
        int(scores[3]), int(scores[4]), int(avg), int(user_id)
    ))

    conn.commit()
    conn.close()


def add_game3_scores(user_id: int, scores: list[int]):
    if len(scores) != 2:
        raise ValueError("Game3 requires exactly 2 scores")

    conn = get_connection()
    cur = conn.cursor()

    columns = _get_columns(cur)

    needed = [
        ("game3_s1", 0),
        ("game3_s2", 0),
        ("game3_avg", 0),
    ]

    for col, default in needed:
        if col not in columns:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT {default}")

    avg = int(round(sum(scores) / 2))

    cur.execute("""
        UPDATE users
        SET game3_s1=?, game3_s2=?, game3_avg=?
        WHERE id=?
    """, (int(scores[0]), int(scores[1]), int(avg), int(user_id)))

    conn.commit()
    conn.close()
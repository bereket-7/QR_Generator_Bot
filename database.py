import sqlite3
from typing import Optional, Dict, List


def init_db():
    conn = sqlite3.connect('qr_bot.db')
    cursor = conn.cursor()

    # Users table (for authentication)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    ''')

    # QR codes table (for CRUD operations)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS qr_codes (
        qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        image_path TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    conn.commit()
    conn.close()


# Initialize the database on import
init_db()

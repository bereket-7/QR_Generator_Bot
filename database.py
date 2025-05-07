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

# User management functions


def add_user(user_id: int, username: str, password: str):
    conn = sqlite3.connect('qr_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users VALUES (?, ?, ?)',
                   (user_id, username, password))
    conn.commit()
    conn.close()


def get_user(username: str) -> Optional[Dict]:
    conn = sqlite3.connect('qr_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return {'user_id': user[0], 'username': user[1], 'password': user[2]} if user else None


# QR code management functions
def save_qr(user_id: int, content: str, image_path: str):
    conn = sqlite3.connect('qr_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO qr_codes (user_id, content, image_path) VALUES (?, ?, ?)',
                   (user_id, content, image_path))
    conn.commit()
    conn.close()


def get_user_qrs(user_id: int) -> List[Dict]:
    conn = sqlite3.connect('qr_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT qr_id, content FROM qr_codes WHERE user_id = ?', (user_id,))
    qrs = [{'qr_id': row[0], 'content': row[1]} for row in cursor.fetchall()]
    conn.close()
    return qrs


def delete_qr(user_id: int, qr_id: int):
    conn = sqlite3.connect('qr_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM qr_codes WHERE user_id = ? AND qr_id = ?', (user_id, qr_id))
    conn.commit()
    conn.close()


# Initialize the database on import
init_db()

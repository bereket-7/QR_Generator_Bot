import sqlite3
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import logging
from auth import auth_manager

logger = logging.getLogger(__name__)


def init_db():
    """Initialize database with secure schema"""
    conn = sqlite3.connect('qr_bot.db')
    cursor = conn.cursor()

    # Users table with secure password storage
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT,
        telegram_id INTEGER UNIQUE,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        login_attempts INTEGER DEFAULT 0,
        locked_until TIMESTAMP
    )
    ''')

    # QR codes table with enhanced metadata
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS qr_codes (
        qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        image_path TEXT NOT NULL,
        title TEXT,
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        scan_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    )
    ''')

    # QR analytics table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS qr_analytics (
        analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
        qr_id INTEGER NOT NULL,
        scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        user_agent TEXT,
        country TEXT,
        city TEXT,
        FOREIGN KEY (qr_id) REFERENCES qr_codes (qr_id) ON DELETE CASCADE
    )
    ''')

    # User sessions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        telegram_chat_id INTEGER NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    )
    ''')

    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_qr_codes_user_id ON qr_codes(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_qr_analytics_qr_id ON qr_analytics(qr_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


def add_user(username: str, password: str, email: Optional[str] = None, telegram_id: Optional[int] = None) -> Tuple[bool, str]:
    """Add new user with secure password hashing"""
    try:
        # Validate input
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters long"
        
        if not password or len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        # Hash password
        password_hash = auth_manager.hash_password(password)
        
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO users (username, password_hash, email, telegram_id)
        VALUES (?, ?, ?, ?)
        ''', (username, password_hash, email, telegram_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"User {username} created successfully")
        return True, "User created successfully"
        
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return False, "Username already exists"
        elif "telegram_id" in str(e):
            return False, "Telegram ID already registered"
        else:
            logger.error(f"Database integrity error: {e}")
            return False, "Registration failed"
    except Exception as e:
        logger.error(f"User creation error: {e}")
        return False, "Registration failed"


def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[int], str]:
    """Authenticate user with rate limiting and account lockout"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        # Get user data
        cursor.execute('''
        SELECT user_id, password_hash, login_attempts, locked_until, is_active
        FROM users WHERE username = ?
        ''', (username,))
        
        user_data = cursor.fetchone()
        
        if not user_data:
            conn.close()
            return False, None, "Invalid username or password"
        
        user_id, password_hash, login_attempts, locked_until, is_active = user_data
        
        # Check if account is locked
        if locked_until:
            locked_time = datetime.fromisoformat(locked_until)
            if datetime.now() < locked_time:
                conn.close()
                return False, None, f"Account locked until {locked_time.strftime('%Y-%m-%d %H:%M')}"
            else:
                # Unlock account if lock period has passed
                cursor.execute('''
                UPDATE users SET login_attempts = 0, locked_until = NULL
                WHERE user_id = ?
                ''', (user_id,))
        
        # Check if account is active
        if not is_active:
            conn.close()
            return False, None, "Account is deactivated"
        
        # Verify password
        if auth_manager.verify_password(password, password_hash):
            # Reset login attempts on successful login
            cursor.execute('''
            UPDATE users SET login_attempts = 0, last_login = CURRENT_TIMESTAMP
            WHERE user_id = ?
            ''', (user_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"User {username} authenticated successfully")
            return True, user_id, "Login successful"
        else:
            # Increment login attempts
            login_attempts += 1
            max_attempts = 5
            
            if login_attempts >= max_attempts:
                # Lock account for 30 minutes
                lock_time = datetime.now() + timedelta(minutes=30)
                cursor.execute('''
                UPDATE users SET login_attempts = ?, locked_until = ?
                WHERE user_id = ?
                ''', (login_attempts, lock_time.isoformat(), user_id))
                
                conn.commit()
                conn.close()
                logger.warning(f"User {username} account locked due to too many failed attempts")
                return False, None, f"Account locked for 30 minutes due to too many failed attempts"
            else:
                # Update login attempts
                cursor.execute('''
                UPDATE users SET login_attempts = ?
                WHERE user_id = ?
                ''', (login_attempts, user_id))
                
                remaining = max_attempts - login_attempts
                conn.commit()
                conn.close()
                
                logger.warning(f"Failed login attempt {login_attempts} for user {username}")
                return False, None, f"Invalid password. {remaining} attempts remaining"
                
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return False, None, "Authentication failed"


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT user_id, username, email, telegram_id, is_active, created_at, last_login
        FROM users WHERE user_id = ? AND is_active = 1
        ''', (user_id,))
        
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            return {
                'user_id': user_data[0],
                'username': user_data[1],
                'email': user_data[2],
                'telegram_id': user_data[3],
                'is_active': user_data[4],
                'created_at': user_data[5],
                'last_login': user_data[6]
            }
        return None
        
    except Exception as e:
        logger.error(f"Get user error: {e}")
        return None


def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict]:
    """Get user by Telegram ID"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT user_id, username, email, telegram_id, is_active, created_at, last_login
        FROM users WHERE telegram_id = ? AND is_active = 1
        ''', (telegram_id,))
        
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            return {
                'user_id': user_data[0],
                'username': user_data[1],
                'email': user_data[2],
                'telegram_id': user_data[3],
                'is_active': user_data[4],
                'created_at': user_data[5],
                'last_login': user_data[6]
            }
        return None
        
    except Exception as e:
        logger.error(f"Get user by telegram ID error: {e}")
        return None


def link_telegram_account(user_id: int, telegram_id: int) -> Tuple[bool, str]:
    """Link Telegram account to user"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        # Check if Telegram ID is already linked to another account
        cursor.execute('SELECT user_id FROM users WHERE telegram_id = ?', (telegram_id,))
        existing = cursor.fetchone()
        
        if existing and existing[0] != user_id:
            conn.close()
            return False, "Telegram ID is already linked to another account"
        
        # Link the account
        cursor.execute('''
        UPDATE users SET telegram_id = ? WHERE user_id = ?
        ''', (telegram_id, user_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Telegram account {telegram_id} linked to user {user_id}")
        return True, "Telegram account linked successfully"
        
    except Exception as e:
        logger.error(f"Link Telegram account error: {e}")
        return False, "Failed to link Telegram account"

# QR Code management functions


def save_qr(user_id: int, content: str, image_path: str, title: Optional[str] = None, 
           description: Optional[str] = None, expires_at: Optional[datetime] = None) -> Tuple[bool, str]:
    """Save QR code with enhanced metadata"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO qr_codes (user_id, content, image_path, title, description, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, content, image_path, title, description, 
              expires_at.isoformat() if expires_at else None))
        
        conn.commit()
        conn.close()
        
        logger.info(f"QR code saved for user {user_id}")
        return True, "QR code saved successfully"
        
    except Exception as e:
        logger.error(f"Save QR error: {e}")
        return False, "Failed to save QR code"


def get_user_qrs(user_id: int) -> List[Dict]:
    """Get all QR codes for a user"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT qr_id, content, image_path, title, description, is_active, 
               scan_count, created_at, expires_at
        FROM qr_codes 
        WHERE user_id = ? AND is_active = 1
        ORDER BY created_at DESC
        ''', (user_id,))
        
        qr_data = cursor.fetchall()
        conn.close()
        
        return [{
            'qr_id': row[0],
            'content': row[1],
            'image_path': row[2],
            'title': row[3],
            'description': row[4],
            'is_active': row[5],
            'scan_count': row[6],
            'created_at': row[7],
            'expires_at': row[8]
        } for row in qr_data]
        
    except Exception as e:
        logger.error(f"Get user QRs error: {e}")
        return []


def delete_qr(qr_id: int, user_id: int) -> Tuple[bool, str]:
    """Delete QR code (soft delete)"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        # Soft delete by marking as inactive
        cursor.execute('''
        UPDATE qr_codes SET is_active = 0 
        WHERE qr_id = ? AND user_id = ?
        ''', (qr_id, user_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return False, "QR code not found or access denied"
        
        conn.commit()
        conn.close()
        
        logger.info(f"QR code {qr_id} deleted by user {user_id}")
        return True, "QR code deleted successfully"
        
    except Exception as e:
        logger.error(f"Delete QR error: {e}")
        return False, "Failed to delete QR code"


def get_qr_by_id(qr_id: int, user_id: int) -> Optional[Dict]:
    """Get specific QR code by ID"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT qr_id, content, image_path, title, description, is_active,
               scan_count, created_at, expires_at
        FROM qr_codes 
        WHERE qr_id = ? AND user_id = ? AND is_active = 1
        ''', (qr_id, user_id))
        
        qr_data = cursor.fetchone()
        conn.close()
        
        if qr_data:
            return {
                'qr_id': qr_data[0],
                'content': qr_data[1],
                'image_path': qr_data[2],
                'title': qr_data[3],
                'description': qr_data[4],
                'is_active': qr_data[5],
                'scan_count': qr_data[6],
                'created_at': qr_data[7],
                'expires_at': qr_data[8]
            }
        return None
        
    except Exception as e:
        logger.error(f"Get QR by ID error: {e}")
        return None


def increment_qr_scan_count(qr_id: int) -> bool:
    """Increment QR code scan count"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE qr_codes SET scan_count = scan_count + 1 
        WHERE qr_id = ?
        ''', (qr_id,))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Increment scan count error: {e}")
        return False


def record_qr_analytics(qr_id: int, ip_address: Optional[str] = None, 
                       user_agent: Optional[str] = None, country: Optional[str] = None,
                       city: Optional[str] = None) -> bool:
    """Record QR code analytics"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO qr_analytics (qr_id, ip_address, user_agent, country, city)
        VALUES (?, ?, ?, ?, ?)
        ''', (qr_id, ip_address, user_agent, country, city))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Record QR analytics error: {e}")
        return False


def get_qr_analytics(qr_id: int, user_id: int) -> List[Dict]:
    """Get analytics for a specific QR code"""
    try:
        # First verify user owns the QR code
        qr = get_qr_by_id(qr_id, user_id)
        if not qr:
            return []
        
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT analytics_id, scanned_at, ip_address, user_agent, country, city
        FROM qr_analytics 
        WHERE qr_id = ?
        ORDER BY scanned_at DESC
        LIMIT 100
        ''', (qr_id,))
        
        analytics_data = cursor.fetchall()
        conn.close()
        
        return [{
            'analytics_id': row[0],
            'scanned_at': row[1],
            'ip_address': row[2],
            'user_agent': row[3],
            'country': row[4],
            'city': row[5]
        } for row in analytics_data]
        
    except Exception as e:
        logger.error(f"Get QR analytics error: {e}")
        return []


def create_user_session(user_id: int, telegram_chat_id: int) -> Tuple[bool, str]:
    """Create user session"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        # Deactivate existing sessions for this chat
        cursor.execute('''
        UPDATE user_sessions SET is_active = 0 
        WHERE telegram_chat_id = ?
        ''', (telegram_chat_id,))
        
        # Create new session
        cursor.execute('''
        INSERT INTO user_sessions (user_id, telegram_chat_id)
        VALUES (?, ?)
        ''', (user_id, telegram_chat_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Session created for user {user_id}")
        return True, "Session created successfully"
        
    except Exception as e:
        logger.error(f"Create session error: {e}")
        return False, "Failed to create session"


def get_active_session(telegram_chat_id: int) -> Optional[Dict]:
    """Get active session for Telegram chat"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT session_id, user_id, telegram_chat_id, created_at, last_activity
        FROM user_sessions 
        WHERE telegram_chat_id = ? AND is_active = 1
        ORDER BY created_at DESC
        LIMIT 1
        ''', (telegram_chat_id,))
        
        session_data = cursor.fetchone()
        conn.close()
        
        if session_data:
            return {
                'session_id': session_data[0],
                'user_id': session_data[1],
                'telegram_chat_id': session_data[2],
                'created_at': session_data[3],
                'last_activity': session_data[4]
            }
        return None
        
    except Exception as e:
        logger.error(f"Get active session error: {e}")
        return None


def update_session_activity(session_id: int) -> bool:
    """Update session last activity"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE user_sessions SET last_activity = CURRENT_TIMESTAMP
        WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Update session activity error: {e}")
        return False


def logout_user(telegram_chat_id: int) -> Tuple[bool, str]:
    """Logout user from Telegram chat"""
    try:
        conn = sqlite3.connect('qr_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE user_sessions SET is_active = 0 
        WHERE telegram_chat_id = ?
        ''', (telegram_chat_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"User logged out from chat {telegram_chat_id}")
        return True, "Logged out successfully"
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return False, "Failed to logout"


# Initialize the database on import
init_db()

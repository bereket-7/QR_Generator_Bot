import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
from database import (
    add_user, authenticate_user, get_user_by_id, get_user_by_telegram_id,
    link_telegram_account, save_qr, get_user_qrs, delete_qr, get_qr_by_id,
    create_user_session, get_active_session, update_session_activity, logout_user,
    increment_qr_scan_count, record_qr_analytics
)
from auth import auth_manager
from validators import (
    validate_user_registration, validate_login_input, validate_qr_creation,
    InputValidator
)
from logger_config import setup_logging, security_logger, audit_logger, log_exception
from app_config import config
import qrcode
from io import BytesIO
import os
import pyshorteners
from encryption import encrypt_text, decrypt_text
from telegram import BotCommand, MenuButtonCommands
from telegram.constants import ParseMode
from datetime import datetime, timedelta

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Conversation states
SIGNUP_USERNAME, SIGNUP_PASSWORD, LOGIN_USERNAME, LOGIN_PASSWORD, QR_CONTENT, QR_TITLE, QR_DESCRIPTION = range(
    7)

# Helper function to generate QR and save to disk


def generate_qr(content: str, user_id: int, title: str = None, description: str = None):
    """Generate QR code with enhanced features"""
    try:
        # Validate content
        is_valid, message = InputValidator.validate_qr_content(content)
        if not is_valid:
            raise ValueError(message)
        
        img = qrcode.make(content)
        qr_dir = f"{config.QR_OUTPUT_DIR}/{user_id}"
        os.makedirs(qr_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        content_hash = hash(content) % 10000
        qr_path = f"{qr_dir}/qr_{timestamp}_{content_hash}.png"
        
        img.save(qr_path)
        
        # Save to database
        success, db_message = save_qr(user_id, content, qr_path, title, description)
        if not success:
            # Remove file if database save failed
            if os.path.exists(qr_path):
                os.remove(qr_path)
            raise ValueError(db_message)
        
        logger.info(f"QR generated for user {user_id}: {qr_path}")
        return qr_path
        
    except Exception as e:
        logger.error(f"QR generation failed: {e}")
        raise

# Start command - shows auth options


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command with enhanced authentication"""
    chat_id = update.effective_chat.id
    
    # Check if user already has an active session
    session = get_active_session(chat_id)
    if session:
        user = get_user_by_id(session['user_id'])
        if user:
            await update.message.reply_text(
                f"Welcome back, {user['username']}! 👋\n\n"
                "You're already logged in. Use /logout to switch accounts."
            )
            return
    
    keyboard = [
        [InlineKeyboardButton("Sign Up", callback_data="signup")],
        [InlineKeyboardButton("Login", callback_data="login")]
    ]
    await update.message.reply_text(
        "🔐 Welcome to Advanced QR Bot!\n\n"
        "Please sign up or login to continue:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Signup flow


async def handle_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle signup initiation"""
    chat_id = update.effective_chat.id
    
    # Rate limiting check
    if auth_manager.is_rate_limited(chat_id, "signup", limit=3, window=300):
        await update.callback_query.message.reply_text(
            "⚠️ Too many signup attempts. Please try again in 5 minutes."
        )
        return ConversationHandler.END
    
    await update.callback_query.message.reply_text(
        "📝 Let's create your account!\n\n"
        "Enter a username (3-30 characters, letters/numbers/_/- only):"
    )
    return SIGNUP_USERNAME


async def signup_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle username input during signup"""
    username = InputValidator.sanitize_input(update.message.text)
    
    # Validate username
    is_valid, message = InputValidator.validate_username(username)
    if not is_valid:
        await update.message.reply_text(f"❌ {message}\n\nPlease try again:")
        return SIGNUP_USERNAME
    
    context.user_data['username'] = username
    await update.message.reply_text(
        "✅ Username accepted!\n\n"
        "Enter a strong password (8+ chars, include uppercase, lowercase, number, and special character):"
    )
    return SIGNUP_PASSWORD


@log_exception
async def signup_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle password input and complete signup"""
    username = context.user_data['username']
    password = update.message.text
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Validate password
    is_valid, message = InputValidator.validate_password(password)
    if not is_valid:
        await update.message.reply_text(f"❌ {message}\n\nPlease try again:")
        return SIGNUP_PASSWORD
    
    # Create user account
    success, result_message = add_user(username, password, telegram_id=telegram_id)
    
    if success:
        # Create session
        user = get_user_by_telegram_id(telegram_id)
        if user:
            create_user_session(user['user_id'], chat_id)
            
            # Log registration
            audit_logger.log_user_registration(user['user_id'], username, telegram_id)
            security_logger.log_login_attempt(username, True, str(chat_id))
            
            await update.message.reply_text(
                f"🎉 Account created successfully!\n\n"
                f"Welcome, {username}! 👋\n\n"
                f"Use /newqr to create your first QR code."
            )
    else:
        await update.message.reply_text(f"❌ {result_message}")
        
        # Log failed registration attempt
        security_logger.log_login_attempt(username, False, str(chat_id))
    
    return ConversationHandler.END

# Login flow (similar to signup)


async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle login initiation"""
    chat_id = update.effective_chat.id
    
    # Rate limiting check
    if auth_manager.is_rate_limited(chat_id, "login", limit=5, window=300):
        await update.callback_query.message.reply_text(
            "⚠️ Too many login attempts. Please try again in 5 minutes."
        )
        return ConversationHandler.END
    
    await update.callback_query.message.reply_text(
        "🔐 Welcome back!\n\n"
        "Enter your username:"
    )
    return LOGIN_USERNAME


async def login_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle username input during login"""
    username = InputValidator.sanitize_input(update.message.text)
    
    # Basic validation
    if not username or len(username) < 1:
        await update.message.reply_text("❌ Username is required. Please try again:")
        return LOGIN_USERNAME
    
    context.user_data['username'] = username
    await update.message.reply_text("Enter your password:")
    return LOGIN_PASSWORD


@log_exception
async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle password input and complete login"""
    username = context.user_data['username']
    password = update.message.text
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Authenticate user
    success, user_id, message = authenticate_user(username, password)
    
    if success and user_id:
        # Link Telegram account if not already linked
        user = get_user_by_id(user_id)
        if user and not user.get('telegram_id'):
            link_telegram_account(user_id, telegram_id)
        
        # Create session
        create_user_session(user_id, chat_id)
        
        # Generate JWT token
        token = auth_manager.generate_token(user_id, username)
        
        # Log successful login
        audit_logger.log_user_login(user_id, username)
        security_logger.log_login_attempt(username, True, str(chat_id))
        
        await update.message.reply_text(
            f"✅ Login successful!\n\n"
            f"Welcome back, {username}! 👋\n\n"
            f"Your session is active for 24 hours.\n"
            f"Use /newqr to create QR codes."
        )
    else:
        # Log failed login attempt
        security_logger.log_login_attempt(username, False, str(chat_id))
        
        if "locked" in message.lower():
            security_logger.log_account_lock(username)
        
        await update.message.reply_text(f"❌ {message}\n\nUse /start to try again.")
    
    return ConversationHandler.END


@log_exception
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile"""
    chat_id = update.effective_chat.id
    
    # Check authentication
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ You need to login first. Use /start to login."
        )
        return
    
    user = get_user_by_id(session['user_id'])
    if not user:
        await update.message.reply_text("❌ User not found. Please login again.")
        return
    
    qrs = get_user_qrs(user['user_id'])
    
    # Update session activity
    update_session_activity(session['session_id'])
    
    await update.message.reply_text(
        f"👤 **Your Profile**\n\n"
        f"📝 Username: {user['username']}\n"
        f"📧 Email: {user.get('email', 'Not set')}\n"
        f"🎯 QR Codes Generated: {len(qrs)}\n"
        f"📅 Member Since: {user['created_at'][:10] if user['created_at'] else 'Unknown'}\n"
        f"🔑 Last Login: {user['last_login'][:16] if user['last_login'] else 'Never'}",
        parse_mode=ParseMode.MARKDOWN
    )


@log_exception
async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logout user with secure confirmation"""
    chat_id = update.effective_chat.id
    
    # Check if user has active session
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ You're not logged in."
        )
        return
    
    user = get_user_by_id(session['user_id'])
    if not user:
        await update.message.reply_text("❌ Session invalid. Please login again.")
        return
    
    # Generate secure logout token
    import secrets
    token = secrets.token_urlsafe(32)
    
    # Store logout token in Redis with 5-minute expiry
    auth_manager.redis_client.setex(
        f"logout_token:{user['user_id']}", 
        300,  # 5 minutes
        token
    )
    
    await update.message.reply_text(
        f"🔐 **Logout Confirmation**\n\n"
        f"To confirm logout, use:\n"
        f"`/confirm_logout {token}`\n\n"
        f"⏰ This token expires in 5 minutes.",
        parse_mode=ParseMode.MARKDOWN
    )


@log_exception
async def confirm_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm logout with token"""
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.message.reply_text(
            "❌ Missing logout token!\n\n"
            "Use /logout to generate a new token."
        )
        return
    
    token = context.args[0]
    
    # Get active session
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ No active session found."
        )
        return
    
    user = get_user_by_id(session['user_id'])
    if not user:
        await update.message.reply_text("❌ User not found.")
        return
    
    # Verify logout token
    stored_token = auth_manager.redis_client.get(f"logout_token:{user['user_id']}")
    
    if stored_token and stored_token == token:
        # Logout user
        logout_user(chat_id)
        auth_manager.revoke_token(user['user_id'])
        
        # Remove logout token
        auth_manager.redis_client.delete(f"logout_token:{user['user_id']}")
        
        # Log logout
        audit_logger.log_user_logout(user['user_id'], user['username'])
        
        await update.message.reply_text(
            "✅ **Successfully logged out!**\n\n"
            "All your sessions have been terminated.\n"
            "Use /start to login again.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ Invalid or expired token!\n\n"
            "Use /logout to generate a new token."
        )


# QR Generation flow
@log_exception
async def generate_qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate QR code generation"""
    chat_id = update.effective_chat.id
    
    # Check authentication
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ You need to login first. Use /start to login."
        )
        return ConversationHandler.END
    
    # Rate limiting check
    if auth_manager.is_rate_limited(session['user_id'], "generate_qr", limit=10, window=3600):
        await update.message.reply_text(
            "⚠️ Too many QR codes generated. Please try again in 1 hour."
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🎯 **QR Code Generation**\n\n"
        "Send the text or URL you want to convert to QR:\n\n"
        "💡 You can also add a title and description later.",
        parse_mode=ParseMode.MARKDOWN
    )
    return QR_CONTENT


@log_exception
async def qr_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle QR content input"""
    chat_id = update.effective_chat.id
    content = InputValidator.sanitize_input(update.message.text)
    
    # Get user session
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ Session expired. Please login again."
        )
        return ConversationHandler.END
    
    # Validate content
    is_valid, message = InputValidator.validate_qr_content(content)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {message}\n\nPlease try again:"
        )
        return QR_CONTENT
    
    context.user_data['qr_content'] = content
    
    await update.message.reply_text(
        "✅ Content received!\n\n"
        "Optional: Add a title for your QR code (max 100 chars):\n"
        "Type 'skip' to continue without title."
    )
    return QR_TITLE


@log_exception
async def qr_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle QR title input"""
    chat_id = update.effective_chat.id
    title_input = update.message.text.strip()
    
    # Get user session
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ Session expired. Please login again."
        )
        return ConversationHandler.END
    
    if title_input.lower() != 'skip':
        # Validate title
        is_valid, message = InputValidator.validate_qr_title(title_input)
        if not is_valid:
            await update.message.reply_text(
                f"❌ {message}\n\nPlease try again or type 'skip':"
            )
            return QR_TITLE
        
        context.user_data['qr_title'] = title_input
    
    await update.message.reply_text(
        "✅ Title processed!\n\n"
        "Optional: Add a description (max 500 chars):\n"
        "Type 'skip' to continue without description."
    )
    return QR_DESCRIPTION


@log_exception
async def qr_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle QR description and generate QR"""
    chat_id = update.effective_chat.id
    desc_input = update.message.text.strip()
    
    # Get user session
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ Session expired. Please login again."
        )
        return ConversationHandler.END
    
    if desc_input.lower() != 'skip':
        # Validate description
        is_valid, message = InputValidator.validate_qr_description(desc_input)
        if not is_valid:
            await update.message.reply_text(
                f"❌ {message}\n\nPlease try again or type 'skip':"
            )
            return QR_DESCRIPTION
        
        context.user_data['qr_description'] = desc_input
    
    # Generate QR code
    try:
        content = context.user_data['qr_content']
        title = context.user_data.get('qr_title')
        description = context.user_data.get('qr_description')
        
        qr_path = generate_qr(content, session['user_id'], title, description)
        
        # Log QR creation
        audit_logger.log_qr_created(session['user_id'], qr_path, content[:50])
        
        # Send QR to user
        with open(qr_path, 'rb') as qr_file:
            caption = f"🎯 **Your QR Code**\n\n"
            
            if title:
                caption += f"📝 {title}\n\n"
            
            caption += f"📄 Content: `{content[:100]}{'...' if len(content) > 100 else ''}`\n\n"
            
            if description:
                caption += f"📋 {description}\n\n"
            
            caption += "✨ QR code generated successfully!"
            
            await update.message.reply_photo(
                photo=qr_file,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN
            )
        
    except Exception as e:
        logger.error(f"QR generation failed: {e}")
        await update.message.reply_text(
            "❌ Failed to generate QR code. Please try again."
        )
    
    return ConversationHandler.END


@log_exception
async def list_qrs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List user's QR codes"""
    chat_id = update.effective_chat.id
    
    # Check authentication
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ You need to login first. Use /start to login."
        )
        return
    
    qrs = get_user_qrs(session['user_id'])
    
    if not qrs:
        await update.message.reply_text(
            "📭 You have no saved QR codes.\n\n"
            "Use /newqr to create your first QR code!"
        )
        return
    
    # Update session activity
    update_session_activity(session['session_id'])
    
    keyboard = []
    for qr in qrs[:10]:  # Limit to 10 QR codes
        title = qr['title'] or qr['content'][:30] + '...' if len(qr['content']) > 30 else qr['content']
        keyboard.append([InlineKeyboardButton(
            f"📄 {title}", callback_data=f"view_{qr['qr_id']}")])
    
    if len(qrs) > 10:
        keyboard.append([InlineKeyboardButton(
            f"📋 Show {len(qrs) - 10} more...", callback_data="show_more_qrs")])
    
    await update.message.reply_text(
        f"🎯 **Your QR Codes** ({len(qrs)} total)\n\n"
        "Select a QR code to view:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


@log_exception
async def delete_qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete QR code"""
    chat_id = update.effective_chat.id
    
    # Check authentication
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ You need to login first. Use /start to login."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /deleteqr <qr_id>\n\n"
            "Use /myqrs to see your QR codes and their IDs."
        )
        return
    
    try:
        qr_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid QR ID. Please provide a number."
        )
        return
    
    # Verify QR belongs to user
    qr = get_qr_by_id(qr_id, session['user_id'])
    if not qr:
        await update.message.reply_text(
            "❌ QR code not found or access denied."
        )
        security_logger.log_permission_denied(
            session['user_id'], f"qr_{qr_id}", "delete"
        )
        return
    
    # Delete QR
    success, message = delete_qr(qr_id, session['user_id'])
    
    if success:
        audit_logger.log_qr_deleted(session['user_id'], qr_id)
        await update.message.reply_text(
            f"✅ QR code deleted successfully!\n\n"
            f"📄 {qr['title'] or qr['content'][:50]}"
        )
    else:
        await update.message.reply_text(f"❌ {message}")


@log_exception
async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Personalized greeting"""
    chat_id = update.effective_chat.id
    
    # Check authentication
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "👋 Hello! Please login first.\n\n"
            "Use /start to get started."
        )
        return
    
    user = get_user_by_id(session['user_id'])
    if user:
        # Update session activity
        update_session_activity(session['session_id'])
        
        await update.message.reply_text(
            f"👋 Hello, {user['username']}! 🎉\n\n"
            f"Welcome back to your QR Bot!\n"
            f"Use /newqr to create QR codes or /myqrs to view your collection."
        )
    else:
        await update.message.reply_text(
            "❌ User not found. Please login again."
        )


@log_exception
async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roll dice - fun command"""
    chat_id = update.effective_chat.id
    
    # Check authentication for rate limiting
    session = get_active_session(chat_id)
    if session:
        # Update session activity
        update_session_activity(session['session_id'])
        
        # Rate limiting for fun commands
        if auth_manager.is_rate_limited(session['user_id'], "fun", limit=20, window=3600):
            await update.message.reply_text(
                "⚠️ Too many fun commands. Please try again later."
            )
            return
    
    await update.message.reply_dice(emoji="🎲")


@log_exception
async def meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Meme command - disabled for security"""
    await update.message.reply_text(
        "🚫 This command has been disabled for security reasons.\n\n"
        "Use /newqr to create QR codes instead!"
    )


@log_exception
async def shorten(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """URL shortener with validation"""
    chat_id = update.effective_chat.id
    
    # Check authentication
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ You need to login first. Use /start to login."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /shorten <url>\n\n"
            "Example: /shorten https://example.com"
        )
        return
    
    url = context.args[0]
    
    # Validate URL
    is_valid, message = InputValidator.validate_url(url)
    if not is_valid:
        await update.message.reply_text(f"❌ {message}")
        return
    
    # Rate limiting
    if auth_manager.is_rate_limited(session['user_id'], "shorten", limit=5, window=300):
        await update.message.reply_text(
            "⚠️ Too many URL shortens. Please try again in 5 minutes."
        )
        return
    
    try:
        s = pyshorteners.Shortener()
        short_url = s.tinyurl.short(url)
        
        await update.message.reply_text(
            f"🔗 **Shortened URL**\n\n"
            f"📄 Original: `{url}`\n"
            f"🔗 Short: `{short_url}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"URL shortening failed: {e}")
        await update.message.reply_text(
            "❌ Failed to shorten URL. Please try again."
        )


@log_exception
async def encrypt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Text encryption with validation"""
    chat_id = update.effective_chat.id
    
    # Check authentication
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ You need to login first. Use /start to login."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /encrypt <text>\n\n"
            "Example: /encrypt Hello World"
        )
        return
    
    text = " ".join(context.args)
    
    # Validate text length
    if len(text) > 1000:
        await update.message.reply_text(
            "❌ Text too long. Maximum 1000 characters."
        )
        return
    
    # Rate limiting
    if auth_manager.is_rate_limited(session['user_id'], "encrypt", limit=10, window=300):
        await update.message.reply_text(
            "⚠️ Too many encryption requests. Please try again in 5 minutes."
        )
        return
    
    try:
        encrypted = encrypt_text(text)
        await update.message.reply_text(
            f"🔒 **Encrypted Text**\n\n"
            f"📝 Original: `{text}`\n\n"
            f"🔐 Encrypted: `{encrypted}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        await update.message.reply_text(
            "❌ Encryption failed. Please try again."
        )


@log_exception
async def decrypt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Text decryption with validation"""
    chat_id = update.effective_chat.id
    
    # Check authentication
    session = get_active_session(chat_id)
    if not session:
        await update.message.reply_text(
            "❌ You need to login first. Use /start to login."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /decrypt <encrypted_text>\n\n"
            "Example: /decrypt gAAAAABh..."
        )
        return
    
    encrypted = " ".join(context.args)
    
    # Rate limiting
    if auth_manager.is_rate_limited(session['user_id'], "decrypt", limit=10, window=300):
        await update.message.reply_text(
            "⚠️ Too many decryption requests. Please try again in 5 minutes."
        )
        return
    
    try:
        decrypted = decrypt_text(encrypted)
        await update.message.reply_text(
            f"🔓 **Decrypted Text**\n\n"
            f"🔐 Encrypted: `{encrypted}`\n\n"
            f"📝 Decrypted: `{decrypted}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        await update.message.reply_text(
            "❌ Invalid encrypted text or decryption failed.\n\n"
            "Please check the encrypted text and try again."
        )


async def post_init(application: Application) -> None:
    """Set up bot commands menu and description"""
    commands = [
        BotCommand("start", "Start bot"),
        BotCommand("help", "Show all commands"),
        BotCommand("profile", "View your profile"),
        BotCommand("newqr", "Generate new QR code"),
        BotCommand("myqrs", "List your saved QRs"),
        BotCommand("deleteqr", "Delete a QR code"),
        BotCommand("shorten", "Shorten a URL"),
        BotCommand("logout", "Log out of your account"),
    ]
    await application.bot.set_my_commands(commands)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())


@log_exception
async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available commands with nice formatting"""
    chat_id = update.effective_chat.id
    
    # Check authentication for personalized help
    session = get_active_session(chat_id)
    
    help_text = """
🌟 *Advanced QR Bot Help* 🌟

🔹 *Account Commands:*
/start - Start or reset bot
/profile - View your profile
/logout - Log out of your account

🔹 *QR Code Commands:*
/newqr - Generate a new QR code
/myqrs - List your saved QR codes
/deleteqr [id] - Delete a QR code

🔹 *Utility Commands:*
/shorten [url] - Shorten a long URL
/encrypt [text] - Encrypt text
/decrypt [text] - Decrypt text
/roll - Roll a dice (just for fun!)
/help - Show this help message

💡 *Pro Tip:* You can just send any text or URL and I'll automatically generate a QR code for you!
🔒 *Security:* All actions are logged and rate-limited for your protection.
"""
    
    if session:
        # Update session activity
        update_session_activity(session['session_id'])
        user = get_user_by_id(session['user_id'])
        if user:
            help_text += f"\n👋 *Welcome back, {user['username']}!*"
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


@log_exception
async def show_command_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show command hint when user types '/'"""
    if update.message.text == "/":
        await update.message.reply_text(
            "🔍 Try one of these commands:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "Show All Commands", callback_data="show_help")]
            ])
        )


def main():
    """Main function to run the bot"""
    # Validate configuration
    is_valid, errors = config.validate_config()
    if not is_valid:
        logger.error(f"Configuration validation failed: {errors}")
        return
    
    # Initialize database
    from database import init_db
    init_db()
    
    # Create application
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    application.post_init = post_init
    
    # Auth Conversation Handler
    auth_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_signup, pattern="^signup$"),
            CallbackQueryHandler(handle_login, pattern="^login$")
        ],
        states={
            SIGNUP_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, signup_username)],
            SIGNUP_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, signup_password)],
            LOGIN_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_username)],
            LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)],
        },
        fallbacks=[],
        per_message=True
    )
    
    # QR Generation Conversation Handler
    qr_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('newqr', generate_qr_command)],
        states={
            QR_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, qr_content)],
            QR_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, qr_title)],
            QR_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, qr_description)],
        },
        fallbacks=[]
    )
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(auth_conv_handler)
    application.add_handler(qr_conv_handler)
    application.add_handler(CommandHandler('help', show_help))
    application.add_handler(CommandHandler('profile', profile))
    application.add_handler(CommandHandler('myqrs', list_qrs))
    application.add_handler(CommandHandler('deleteqr', delete_qr_command))
    application.add_handler(CommandHandler('hello', hello))
    application.add_handler(CommandHandler('shorten', shorten))
    application.add_handler(CommandHandler('roll', roll))
    application.add_handler(CommandHandler('meme', meme))
    application.add_handler(CommandHandler('encrypt', encrypt_cmd))
    application.add_handler(CommandHandler('decrypt', decrypt_cmd))
    application.add_handler(CommandHandler('logout', logout))
    application.add_handler(CommandHandler('confirm_logout', confirm_logout))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start bot
    logger.info("Starting Advanced QR Bot...")
    application.run_polling()


if __name__ == '__main__':
    main()

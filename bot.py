from secrets import token_urlsafe
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
from database import add_logout_token, add_user, delete_session, get_user, get_user_by_id, save_qr, get_user_qrs, delete_qr, validate_logout
import qrcode
from io import BytesIO
import os
import pyshorteners
from encryption import encrypt_text, decrypt_text
from config import Config
from telegram import BotCommand, MenuButtonCommands
from telegram.constants import ParseMode

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
SIGNUP_USERNAME, SIGNUP_PASSWORD, LOGIN_USERNAME, LOGIN_PASSWORD, QR_CONTENT = range(
    5)

# Helper function to generate QR and save to disk


def generate_qr(content: str, user_id: int):
    img = qrcode.make(content)
    qr_dir = f"qr_codes/{user_id}"
    os.makedirs(qr_dir, exist_ok=True)
    qr_path = f"{qr_dir}/{hash(content)}.png"
    img.save(qr_path)
    return qr_path

# Start command - shows auth options


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Sign Up", callback_data="signup")],
        [InlineKeyboardButton("Login", callback_data="login")]
    ]
    await update.message.reply_text(
        "Welcome to QR Bot! Please sign up or login:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Signup flow


async def handle_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("Enter a username:")
    return SIGNUP_USERNAME


async def signup_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['username'] = update.message.text
    await update.message.reply_text("Enter a password:")
    return SIGNUP_PASSWORD


async def signup_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data['username']
    password = update.message.text
    user_id = update.effective_user.id

    add_user(user_id, username, password)
    await update.message.reply_text(f"Account created! Hello, {username}!")
    return ConversationHandler.END

# Login flow (similar to signup)


async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("Enter your username:")
    return LOGIN_USERNAME


async def login_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['username'] = update.message.text
    await update.message.reply_text("Enter your password:")
    return LOGIN_PASSWORD


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data['username']
    password = update.message.text
    user = get_user(username)

    if user and user['password'] == password:
        await update.message.reply_text(f"Welcome back, {username}!")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Invalid credentials. Try /start again.")
        return ConversationHandler.END


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_id(update.effective_user.id)
    await update.message.reply_text(
        f"👤 Your Profile:\n"
        f"Username: {user['username']}\n"
        f"QRs Generated: {len(get_user_qrs(user['user_id']))}"
    )


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    token = token_urlsafe(16)

    # Store logout token in DB
    add_logout_token(user_id, token)

    # Send confirmation with secure token
    await update.message.reply_text(
        f"⚠️ Confirm logout by clicking: /confirm_logout {token}\n"
        "This token expires in 5 minutes.",
        parse_mode="Markdown"
    )


async def confirm_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Missing logout token!")
        return

    token = context.args[0]
    if validate_logout(user_id, token):
        delete_session(user_id)
        # Clear user-specific data
        await update.message.reply_text(
            "✅ Successfully logged out!\n"
            "All your sessions have been terminated."
        )
    else:
        await update.message.reply_text("❌ Invalid or expired token!")


# QR Generation flow
async def generate_qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send the text/URL you want to convert to QR:")
    return QR_CONTENT


async def qr_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = update.message.text
    user_id = update.effective_user.id
    qr_path = generate_qr(content, user_id)

    # Save to database
    save_qr(user_id, content, qr_path)

    # Send QR to user
    with open(qr_path, 'rb') as qr_file:
        await update.message.reply_photo(photo=qr_file, caption="Here's your QR code!")
    return ConversationHandler.END


async def list_qrs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    qrs = get_user_qrs(user_id)

    if not qrs:
        await update.message.reply_text("You have no saved QR codes.")
        return

    keyboard = []
    for qr in qrs:
        keyboard.append([InlineKeyboardButton(
            qr['content'], callback_data=f"view_{qr['qr_id']}")])

    await update.message.reply_text(
        "Your saved QR codes:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def delete_qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    qr_id = int(context.args[0]) if context.args else None

    if not qr_id:
        await update.message.reply_text("Usage: /deleteqr <qr_id>")
        return

    delete_qr(user_id, qr_id)
    await update.message.reply_text("QR code deleted!")


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_by_id(user_id)

    if user:
        await update.message.reply_text(f"Hello, {user['username']}! 👋")
    else:
        await update.message.reply_text("You're not registered. Use /start to sign up!")


async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice(emoji="🎲")


async def meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_top, text_bottom = context.args[0], context.args[1]
    await update.message.reply_photo(photo=open("meme.png", "rb"))


async def shorten(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = context.args[0]
    s = pyshorteners.Shortener()
    short_url = s.tinyurl.short(url)
    await update.message.reply_text(f"Short URL: {short_url}")


async def encrypt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /encrypt <text>")
        return

    text = " ".join(context.args)
    encrypted = encrypt_text(text)
    await update.message.reply_text(f"🔒 Encrypted:\n`{encrypted}`", parse_mode="Markdown")


async def decrypt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /decrypt <encrypted_text>")
        return

    encrypted = " ".join(context.args)
    try:
        decrypted = decrypt_text(encrypted)
        await update.message.reply_text(f"🔓 Decrypted:\n`{decrypted}`", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid encrypted text!")


async def post_init(application: Application) -> None:
    """Set up bot commands menu and description"""
    commands = [
        BotCommand("start", "Start the bot"),
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

# Add this new help command handler


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available commands with nice formatting"""
    help_text = """
🌟 *QR Code Bot Help* 🌟

🔹 *Account Commands:*
/start - Start or reset the bot
/profile - View your profile
/logout - Log out of your account

🔹 *QR Code Commands:*
/newqr - Generate a new QR code
/myqrs - List your saved QR codes
/deleteqr [id] - Delete a QR code

🔹 *Utility Commands:*
/shorten [url] - Shorten a long URL
/roll - Roll a dice (just for fun!)
/help - Show this help message

💡 *Pro Tip:* You can just send any text or URL and I'll automatically generate a QR code for you!
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct messages by auto-generating QR codes"""
    user = get_user_by_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please /start to register first!")
        return

    if update.message.text and not update.message.text.startswith('/'):
        # Auto-generate QR for direct text/URL messages
        content = update.message.text
        user_id = update.effective_user.id
        qr_path = generate_qr(content, user_id)
        save_qr(user_id, content, qr_path)

        with open(qr_path, 'rb') as qr_file:
            await update.message.reply_photo(
                photo=qr_file,
                caption=f"Here's your QR code for: {content}",
                parse_mode=ParseMode.MARKDOWN
            )


def main():
    application = Application.builder().token(Config.BOT_TOKEN).build()

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
        },
        fallbacks=[]
    )

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(auth_conv_handler)
    application.add_handler(qr_conv_handler)
    application.add_handler(CommandHandler('myqrs', list_qrs))
    application.add_handler(CommandHandler('deleteqr', delete_qr_command))
    application.add_handler(CommandHandler('hello', hello))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("shorten", shorten))
    application.add_handler(CommandHandler("roll", roll))
    application.add_handler(CommandHandler("meme", meme))
    application.add_handler(CommandHandler("encrypt", encrypt_cmd))
    application.add_handler(CommandHandler("decrypt", decrypt_cmd))
    application.add_handler(CommandHandler("logout", logout))
    application.add_handler(CommandHandler("confirm_logout", confirm_logout))
    application.add_handler(CommandHandler("help", show_help))

    application.add_handler(MessageHandler(
        filters.Text("/"), show_command_hint))
    application.add_handler(CallbackQueryHandler(
        show_help, pattern="^show_help$"))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    application.run_polling()


if __name__ == '__main__':
    main()

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
from database import add_user, get_user, get_user_by_id, save_qr, get_user_qrs, delete_qr
import qrcode
from io import BytesIO
import os
import pyshorteners
from encryption import encrypt_text, decrypt_text
from config import Config

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


def main():
    application = Application.builder().token(Config.BOT_TOKEN).build()

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
        fallbacks=[]
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

    # Start the bot
    application.run_polling()


if __name__ == '__main__':
    main()

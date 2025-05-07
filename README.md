# **QR Code Generator Telegram Bot**

**A Python-based Telegram bot with user authentication (Signup/Login) and CRUD for QR codes.**

![Demo](https://img.shields.io/badge/Demo-Telegram-blue) ![Python](https://img.shields.io/badge/Python-3.8%2B-green) ![License](https://img.shields.io/badge/License-MIT-orange)

## **Features**

✅ **User Authentication** (Signup/Login)  
✅ **Personalized Greetings** (`/hello`)  
✅ **QR Code Generation** (Text/URL → QR)  
✅ **CRUD Operations** (Save, List, Delete QRs)  
✅ **SQLite Database** (Stores users and QRs)

## **Tech Stack**

- **Library**: `python-telegram-bot` (v20.x)
- **QR Generation**: `qrcode` + `Pillow`
- **Database**: SQLite (`sqlite3`)
- **Deployment**: Local/Polling (Heroku-ready)

## **Setup & Installation**

### **1. Clone the Repository**

```bash
git clone https://github.com/bereket-7/QR_Generator_Bot.git
cd QR_Generator_Bot
```

### **2. Install Dependencies**

```bash
pip install -r requirements.txt
```

### **3. Configure the Bot**

1. Get a Telegram bot token from [@BotFather](https://t.me/BotFather).
2. Replace `YOUR_BOT_TOKEN` in `bot.py` with your token.

### **4. Run the Bot**

```bash
python bot.py
```

## **Bot Commands**

| Command          | Description                 | Example                          |
| ---------------- | --------------------------- | -------------------------------- |
| `/start`         | Initiate bot (Signup/Login) | `/start`                         |
| `/hello`         | Personalized greeting       | `/hello`                         |
| `/newqr`         | Generate a new QR code      | `/newqr` → "https://example.com" |
| `/myqrs`         | List your saved QR codes    | `/myqrs`                         |
| `/deleteqr <id>` | Delete a QR code            | `/deleteqr 1`                    |

## **Project Structure**

```
QR_Generator_Bot/
├── bot.py               # Main bot logic (handlers, commands)
├── database.py          # Database setup & utilities
├── requirements.txt     # Dependencies
├── qr_bot.db            # SQLite database (auto-created)
└── qr_codes/            # Folder for saved QR images
```

## **How It Works**

1. **Authentication**:

   - Users sign up/login via `/start`.
   - Credentials stored in SQLite (`users` table).

2. **QR Generation**:

   - User sends text/URL → bot generates QR and saves it to `qr_codes/{user_id}/`.
   - Metadata (user_id, content, path) saved in `qr_codes` table.

3. **CRUD Operations**:
   - **Create**: `/newqr` → Saves QR.
   - **Read**: `/myqrs` → Lists QRs with inline buttons.
   - **Delete**: `/deleteqr <id>` → Removes QR.

## **Screenshots (Demo)**

_(Demo screenshots here.)_

## **Future Improvements**

🔹 **Password Hashing**: Use `bcrypt` for secure storage.  
🔹 **Webhook Deployment**: Deploy on Heroku/Railway.  
🔹 **Admin Panel**: Manage users/QRs via web interface.  
🔹 **QR Batch Export**: Download all QRs as a ZIP.

## **Contributing**

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/xyz`).
3. Commit changes (`git commit -m 'Add feature xyz'`).
4. Push to the branch (`git push origin feature/xyz`).
5. Open a Pull Request.

## **License**

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

## **Support**

🐞 **Found a bug?** Open an [Issue](https://github.com/yourusername/qr-bot/issues).  
💡 **Suggestions?** Feel free to contribute!

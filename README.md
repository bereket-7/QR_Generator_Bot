# **Advanced QR Code Generator Telegram Bot**

**A secure, enterprise-ready Python-based Telegram bot with advanced authentication, rate limiting, and comprehensive logging.**

![Demo](https://img.shields.io/badge/Demo-Telegram-blue) ![Python](https://img.shields.io/badge/Python-3.8%2B-green) ![License](https://img.shields.io/badge/License-MIT-orange) ![Security](https://img.shields.io/badge/Security-Advanced-red)

## **🚀 Major Security Enhancements**

### **Authentication & Authorization**
- ✅ **bcrypt Password Hashing** (12 rounds)
- ✅ **JWT Token Management** with Redis sessions
- ✅ **Account Lockout** after failed attempts (30 min)
- ✅ **Secure Logout** with token confirmation
- ✅ **Session Management** with activity tracking

### **Input Validation & Security**
- ✅ **Comprehensive Input Validation** (XSS, SQL Injection prevention)
- ✅ **Rate Limiting** per user/action
- ✅ **Content Sanitization** for all user inputs
- ✅ **File Upload Security** validation
- ✅ **URL Validation** for malicious content

### **Logging & Monitoring**
- ✅ **Multi-level Logging** (Security, Audit, Performance)
- ✅ **Log Rotation** (10MB files, 5 backups)
- ✅ **Security Event Tracking** (logins, failures, locks)
- ✅ **Audit Trail** for all user actions
- ✅ **Performance Monitoring** for slow operations

## **📋 Enhanced Features**

### **User Management**
- Secure registration with password strength validation
- Email support (optional)
- Telegram account linking
- Profile management with activity tracking
- Multi-device session support

### **QR Code Features**
- Enhanced QR generation with titles and descriptions
- Content validation and sanitization
- Scan analytics tracking
- Soft delete with audit trail
- QR code expiration support

### **Security Features**
- Rate limiting per action type
- Account lockout protection
- Secure token-based logout
- Permission-based access control
- Comprehensive audit logging

## **🛠️ Tech Stack**

### **Core Libraries**
- `python-telegram-bot` (v20.3) - Telegram Bot API
- `bcrypt` (v4.1.2) - Password hashing
- `PyJWT` (v2.8.0) - JWT tokens
- `redis` (v5.0.1) - Session storage & rate limiting
- `validators` (v0.22.0) - Input validation

### **Security Libraries**
- `cryptography` (v44.0.3) - Encryption
- `python-dotenv` (v1.0.0) - Environment management

### **QR & Utilities**
- `qrcode` (v7.4.2) + `Pillow` (v10.0.0) - QR generation
- `pyshorteners` (v1.0.1) - URL shortening

## **📁 Project Structure**

```
QR_Generator_Bot/
├── bot.py                  # Main bot logic (990+ lines)
├── database.py             # Enhanced database with security
├── auth.py                # JWT & authentication manager
├── validators.py           # Input validation & sanitization
├── logger_config.py        # Multi-level logging system
├── app_config.py          # Configuration management
├── encryption.py          # Text encryption utilities
├── requirements.txt       # Updated dependencies
├── .env.example         # Environment template
├── logs/                # Log files directory
│   ├── qr_bot.log       # Main application logs
│   ├── errors.log       # Error-only logs
│   ├── security.log     # Security events
│   ├── audit.log        # User action audit
│   └── performance.log # Performance metrics
├── qr_codes/            # QR code storage
└── qr_bot.db           # SQLite database (enhanced schema)
```

## **🚀 Setup & Installation**

### **1. Clone the Repository**

```bash
git clone https://github.com/bereket-7/QR_Generator_Bot.git
cd QR_Generator_Bot
```

### **2. Install Dependencies**

```bash
pip install -r requirements.txt
```

### **3. Environment Configuration**

```bash
cp .env.example .env
# Edit .env with your configuration
```

**Required Environment Variables:**
```bash
BOT_TOKEN=your_telegram_bot_token
JWT_SECRET=your-super-secret-jwt-key-at-least-32-chars
REDIS_HOST=localhost  # Required for production
REDIS_PORT=6379
```

### **4. Redis Setup (Required for Production)**

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Start Redis
redis-server
```

### **5. Run the Bot**

```bash
python bot.py
```

## **🔒 Security Configuration**

### **Production Security Checklist**

- [ ] Change `JWT_SECRET` to a strong 32+ character key
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure Redis with authentication
- [ ] Set up log rotation for production logs
- [ ] Configure firewall for Redis port
- [ ] Use HTTPS for any web components
- [ ] Regular database backups
- [ ] Monitor security logs

### **Rate Limiting Configuration**

```bash
# Default rate limits (configurable)
RATE_LIMIT_REQUESTS=5      # Requests per window
RATE_LIMIT_WINDOW=300        # 5 minutes
MAX_LOGIN_ATTEMPTS=5        # Before lockout
ACCOUNT_LOCK_MINUTES=30      # Lockout duration
```

## **📊 Enhanced Bot Commands**

| Command | Description | Security Features |
|---------|-------------|------------------|
| `/start` | Secure authentication flow | Session validation |
| `/profile` | User profile with stats | Authentication required |
| `/newqr` | Enhanced QR generation | Rate limited, validated |
| `/myqrs` | List QR codes with pagination | Authentication required |
| `/deleteqr <id>` | Secure QR deletion | Ownership verification |
| `/shorten <url>` | URL shortening | URL validation, rate limited |
| `/encrypt <text>` | Text encryption | Length validation, rate limited |
| `/decrypt <text>` | Text decryption | Rate limited |
| `/logout` | Secure logout | Token confirmation required |
| `/help` | Enhanced help system | Personalized for logged users |

## **🔍 Advanced Features**

### **Session Management**
- Multi-device support
- Activity tracking
- Automatic session expiration
- Secure logout with token confirmation

### **QR Analytics**
- Scan count tracking
- Geographic data (if available)
- Access pattern analysis
- Performance metrics

### **Security Monitoring**
- Failed login attempt tracking
- Account lockout notifications
- Suspicious activity detection
- Comprehensive audit trails

### **Rate Limiting**
- Per-user rate limiting
- Action-specific limits
- Configurable time windows
- Redis-based distributed limiting

## **📈 Performance Features**

### **Database Optimization**
- Indexed queries
- Connection pooling ready
- Soft delete implementation
- Efficient pagination

### **Caching Strategy**
- Redis session storage
- Rate limiting cache
- Performance monitoring
- Log buffering

### **Scalability**
- Microservice-ready architecture
- Database migration scripts
- Environment-based configuration
- Production deployment ready

## **🛡️ Security Best Practices Implemented**

1. **Password Security**
   - bcrypt with 12 rounds
   - Strong password requirements
   - No plain text storage

2. **Session Security**
   - JWT tokens with expiration
   - Redis-based session storage
   - Secure logout implementation

3. **Input Validation**
   - XSS prevention
   - SQL injection protection
   - Content sanitization
   - File upload validation

4. **Rate Limiting**
   - Prevents brute force attacks
   - Action-specific limits
   - Distributed Redis implementation

5. **Logging & Monitoring**
   - Security event tracking
   - Comprehensive audit trails
   - Performance monitoring
   - Log rotation

## **🚀 Deployment**

### **Development**
```bash
ENVIRONMENT=development python bot.py
```

### **Production**
```bash
ENVIRONMENT=production \
JWT_SECRET=your-production-secret \
REDIS_HOST=your-redis-host \
python bot.py
```

### **Docker Support**
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

## **📊 Monitoring & Maintenance**

### **Log Files**
- `logs/qr_bot.log` - Main application logs
- `logs/security.log` - Security events
- `logs/audit.log` - User actions
- `logs/performance.log` - Performance metrics
- `logs/errors.log` - Error-only logs

### **Health Checks**
- Database connectivity
- Redis connection status
- Token validation
- Rate limiting functionality

## **🔄 Migration from Basic Version**

The advanced version includes breaking changes for security:

1. **Database Schema** - Enhanced with security fields
2. **Authentication** - JWT-based instead of basic
3. **Configuration** - Environment-based
4. **Dependencies** - New security libraries

**Migration Steps:**
1. Backup existing database
2. Install new dependencies
3. Update configuration
4. Run with `init_db()` for schema migration
5. Test authentication flow

## **🤝 Contributing**

1. Fork the repository
2. Create feature branch (`git checkout -b feature/security-enhancement`)
3. Commit with security-focused changes
4. Push to branch
5. Open Pull Request

**Security contributions welcome!**

## **📄 License**

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

## **🆘 Support & Security**

- 🐛 **Bug Reports**: Open an Issue
- 🔒 **Security Issues**: Private message only
- 💡 **Feature Requests**: Discussions welcome
- 📧 **Contact**: Create GitHub Issue

---

**⚠️ Security Notice**: This bot implements enterprise-grade security features. Always review security configurations before production deployment.

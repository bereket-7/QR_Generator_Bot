import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


class Config:
    """Application configuration"""
    
    # Bot Configuration
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    
    # Database Configuration
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///qr_bot.db')
    
    # Redis Configuration
    REDIS_HOST: str = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT: int = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB: int = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD: Optional[str] = os.getenv('REDIS_PASSWORD')
    
    # JWT Configuration
    JWT_SECRET: str = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
    JWT_ALGORITHM: str = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRY_HOURS: int = int(os.getenv('JWT_EXPIRY_HOURS', 24))
    
    # Security Configuration
    BCRYPT_ROUNDS: int = int(os.getenv('BCRYPT_ROUNDS', 12))
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv('MAX_LOGIN_ATTEMPTS', 5))
    ACCOUNT_LOCK_MINUTES: int = int(os.getenv('ACCOUNT_LOCK_MINUTES', 30))
    
    # Rate Limiting Configuration
    RATE_LIMIT_REQUESTS: int = int(os.getenv('RATE_LIMIT_REQUESTS', 5))
    RATE_LIMIT_WINDOW: int = int(os.getenv('RATE_LIMIT_WINDOW', 300))  # 5 minutes
    
    # File Upload Configuration
    MAX_FILE_SIZE: int = int(os.getenv('MAX_FILE_SIZE', 10 * 1024 * 1024))  # 10MB
    ALLOWED_FILE_TYPES: list = os.getenv('ALLOWED_FILE_TYPES', 'png,jpg,jpeg,gif').split(',')
    
    # QR Code Configuration
    QR_MAX_CONTENT_LENGTH: int = int(os.getenv('QR_MAX_CONTENT_LENGTH', 4296))
    QR_DEFAULT_SIZE: int = int(os.getenv('QR_DEFAULT_SIZE', 200))
    QR_OUTPUT_DIR: str = os.getenv('QR_OUTPUT_DIR', 'qr_codes')
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: str = os.getenv('LOG_FILE', 'qr_bot.log')
    
    # Environment
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'development')
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    
    @classmethod
    def validate_config(cls) -> tuple[bool, list[str]]:
        """Validate required configuration"""
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is required")
        
        if cls.ENVIRONMENT == 'production' and cls.JWT_SECRET == 'your-secret-key-change-in-production':
            errors.append("JWT_SECRET must be changed in production")
        
        if cls.JWT_SECRET and len(cls.JWT_SECRET) < 32:
            errors.append("JWT_SECRET should be at least 32 characters long")
        
        return len(errors) == 0, errors
    
    @classmethod
    def get_database_url(cls) -> str:
        """Get database URL based on environment"""
        if cls.ENVIRONMENT == 'production' and cls.DATABASE_URL.startswith('sqlite'):
            raise ValueError("SQLite should not be used in production")
        return cls.DATABASE_URL
    
    @classmethod
    def is_development(cls) -> bool:
        """Check if running in development mode"""
        return cls.ENVIRONMENT == 'development'
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production mode"""
        return cls.ENVIRONMENT == 'production'


# Create global config instance
config = Config()

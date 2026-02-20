import logging
import logging.handlers
import os
from datetime import datetime
from app_config import config


def setup_logging():
    """Setup enhanced logging configuration"""
    
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # File handler for all logs
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, config.LOG_FILE),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'errors.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)
    
    # Security log handler
    security_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'security.log'),
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    security_handler.setLevel(logging.WARNING)
    security_handler.setFormatter(detailed_formatter)
    
    # Create security logger
    security_logger = logging.getLogger('security')
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.WARNING)
    
    # Set specific logger levels
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    logger.info(f"Logging initialized - Level: {config.LOG_LEVEL}, Environment: {config.ENVIRONMENT}")


class SecurityLogger:
    """Specialized logger for security events"""
    
    def __init__(self):
        self.logger = logging.getLogger('security')
    
    def log_login_attempt(self, username: str, success: bool, ip_address: str = None):
        """Log login attempt"""
        status = "SUCCESS" if success else "FAILED"
        message = f"LOGIN_ATTEMPT - Username: {username}, Status: {status}"
        if ip_address:
            message += f", IP: {ip_address}"
        self.logger.warning(message)
    
    def log_account_lock(self, username: str, reason: str = "too many failed attempts"):
        """Log account lock event"""
        self.logger.error(f"ACCOUNT_LOCKED - Username: {username}, Reason: {reason}")
    
    def log_suspicious_activity(self, user_id: int, activity: str, details: str = None):
        """Log suspicious activity"""
        message = f"SUSPICIOUS_ACTIVITY - User ID: {user_id}, Activity: {activity}"
        if details:
            message += f", Details: {details}"
        self.logger.warning(message)
    
    def log_permission_denied(self, user_id: int, resource: str, action: str):
        """Log permission denied event"""
        self.logger.warning(f"PERMISSION_DENIED - User ID: {user_id}, Resource: {resource}, Action: {action}")
    
    def log_data_access(self, user_id: int, resource: str, action: str):
        """Log data access events"""
        message = f"DATA_ACCESS - User ID: {user_id}, Resource: {resource}, Action: {action}"
        if config.DEBUG:
            self.logger.info(message)
    
    def log_rate_limit_exceeded(self, user_id: int, action: str):
        """Log rate limit exceeded"""
        self.logger.warning(f"RATE_LIMIT_EXCEEDED - User ID: {user_id}, Action: {action}")


class AuditLogger:
    """Specialized logger for audit events"""
    
    def __init__(self):
        self.logger = logging.getLogger('audit')
        
        # Create audit log file handler
        if not self.logger.handlers:
            audit_handler = logging.handlers.RotatingFileHandler(
                filename=os.path.join('logs', 'audit.log'),
                maxBytes=20 * 1024 * 1024,  # 20MB
                backupCount=10,
                encoding='utf-8'
            )
            audit_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - AUDIT - %(message)s'
            )
            audit_handler.setFormatter(formatter)
            self.logger.addHandler(audit_handler)
            self.logger.setLevel(logging.INFO)
    
    def log_user_registration(self, user_id: int, username: str, telegram_id: int = None):
        """Log user registration"""
        message = f"USER_REGISTERED - ID: {user_id}, Username: {username}"
        if telegram_id:
            message += f", Telegram ID: {telegram_id}"
        self.logger.info(message)
    
    def log_user_login(self, user_id: int, username: str):
        """Log user login"""
        self.logger.info(f"USER_LOGIN - ID: {user_id}, Username: {username}")
    
    def log_user_logout(self, user_id: int, username: str):
        """Log user logout"""
        self.logger.info(f"USER_LOGOUT - ID: {user_id}, Username: {username}")
    
    def log_qr_created(self, user_id: int, qr_id: int, content_preview: str):
        """Log QR code creation"""
        preview = content_preview[:50] + "..." if len(content_preview) > 50 else content_preview
        self.logger.info(f"QR_CREATED - User ID: {user_id}, QR ID: {qr_id}, Content: {preview}")
    
    def log_qr_deleted(self, user_id: int, qr_id: int):
        """Log QR code deletion"""
        self.logger.info(f"QR_DELETED - User ID: {user_id}, QR ID: {qr_id}")
    
    def log_qr_accessed(self, user_id: int, qr_id: int):
        """Log QR code access"""
        self.logger.info(f"QR_ACCESSED - User ID: {user_id}, QR ID: {qr_id}")
    
    def log_data_export(self, user_id: int, data_type: str, record_count: int):
        """Log data export events"""
        self.logger.info(f"DATA_EXPORT - User ID: {user_id}, Type: {data_type}, Records: {record_count}")


class PerformanceLogger:
    """Specialized logger for performance monitoring"""
    
    def __init__(self):
        self.logger = logging.getLogger('performance')
        
        # Create performance log file handler
        if not self.logger.handlers:
            perf_handler = logging.handlers.RotatingFileHandler(
                filename=os.path.join('logs', 'performance.log'),
                maxBytes=5 * 1024 * 1024,  # 5MB
                backupCount=3,
                encoding='utf-8'
            )
            perf_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - PERFORMANCE - %(message)s'
            )
            perf_handler.setFormatter(formatter)
            self.logger.addHandler(perf_handler)
            self.logger.setLevel(logging.INFO)
    
    def log_slow_query(self, query: str, duration: float):
        """Log slow database queries"""
        if duration > 1.0:  # Log queries taking more than 1 second
            self.logger.warning(f"SLOW_QUERY - Duration: {duration:.2f}s, Query: {query[:100]}...")
    
    def log_api_response_time(self, endpoint: str, duration: float, status_code: int):
        """Log API response times"""
        if duration > 2.0:  # Log slow responses
            self.logger.warning(f"SLOW_RESPONSE - Endpoint: {endpoint}, Duration: {duration:.2f}s, Status: {status_code}")
    
    def log_memory_usage(self, component: str, memory_mb: float):
        """Log memory usage"""
        self.logger.info(f"MEMORY_USAGE - Component: {component}, Memory: {memory_mb:.2f}MB")


# Create global logger instances
security_logger = SecurityLogger()
audit_logger = AuditLogger()
performance_logger = PerformanceLogger()


def log_exception(func):
    """Decorator to log exceptions in functions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger = logging.getLogger(func.__module__)
            logger.error(f"Exception in {func.__name__}: {str(e)}", exc_info=True)
            raise
    return wrapper

import re
import validators
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom validation error"""
    pass


class InputValidator:
    """Input validation and sanitization utilities"""
    
    @staticmethod
    def validate_username(username: str) -> Tuple[bool, str]:
        """Validate username format"""
        if not username:
            return False, "Username is required"
        
        if len(username) < 3:
            return False, "Username must be at least 3 characters long"
        
        if len(username) > 30:
            return False, "Username must be less than 30 characters"
        
        # Allow only alphanumeric, underscores, and hyphens
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            return False, "Username can only contain letters, numbers, underscores, and hyphens"
        
        # Prevent SQL injection patterns
        if any(pattern in username.lower() for pattern in ['drop', 'delete', 'insert', 'update', 'select']):
            return False, "Invalid username format"
        
        return True, "Valid username"
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """Validate password strength"""
        if not password:
            return False, "Password is required"
        
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if len(password) > 128:
            return False, "Password must be less than 128 characters"
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        # Check for at least one digit
        if not re.search(r'\d', password):
            return False, "Password must contain at least one digit"
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
        
        return True, "Valid password"
    
    @staticmethod
    def validate_email(email: Optional[str]) -> Tuple[bool, str]:
        """Validate email format"""
        if not email:
            return True, "Email is optional"  # Email is optional
        
        if len(email) > 255:
            return False, "Email must be less than 255 characters"
        
        if not validators.email(email):
            return False, "Invalid email format"
        
        return True, "Valid email"
    
    @staticmethod
    def validate_url(url: str) -> Tuple[bool, str]:
        """Validate URL format"""
        if not url:
            return False, "URL is required"
        
        if len(url) > 2048:
            return False, "URL must be less than 2048 characters"
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        if not validators.url(url):
            return False, "Invalid URL format"
        
        return True, "Valid URL"
    
    @staticmethod
    def validate_qr_content(content: str) -> Tuple[bool, str]:
        """Validate QR code content"""
        if not content:
            return False, "Content is required"
        
        if len(content) > 4296:  # QR code max data capacity
            return False, "Content is too long for QR code (max 4296 characters)"
        
        # Check for malicious content patterns
        malicious_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',               # JavaScript protocol
            r'data:',                    # Data protocol
            r'vbscript:',                # VBScript protocol
        ]
        
        for pattern in malicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False, "Content contains potentially malicious code"
        
        return True, "Valid content"
    
    @staticmethod
    def validate_qr_title(title: Optional[str]) -> Tuple[bool, str]:
        """Validate QR code title"""
        if not title:
            return True, "Title is optional"
        
        if len(title) > 100:
            return False, "Title must be less than 100 characters"
        
        # Sanitize title - remove HTML tags
        title = re.sub(r'<[^>]+>', '', title)
        
        # Check for malicious patterns
        if any(pattern in title.lower() for pattern in ['script', 'javascript', 'vbscript']):
            return False, "Title contains invalid content"
        
        return True, "Valid title"
    
    @staticmethod
    def validate_qr_description(description: Optional[str]) -> Tuple[bool, str]:
        """Validate QR code description"""
        if not description:
            return True, "Description is optional"
        
        if len(description) > 500:
            return False, "Description must be less than 500 characters"
        
        # Sanitize description - remove HTML tags
        description = re.sub(r'<[^>]+>', '', description)
        
        # Check for malicious patterns
        if any(pattern in description.lower() for pattern in ['script', 'javascript', 'vbscript']):
            return False, "Description contains invalid content"
        
        return True, "Valid description"
    
    @staticmethod
    def validate_telegram_id(telegram_id: int) -> Tuple[bool, str]:
        """Validate Telegram user ID"""
        if not isinstance(telegram_id, int):
            return False, "Telegram ID must be a number"
        
        if telegram_id <= 0:
            return False, "Invalid Telegram ID"
        
        # Telegram IDs are typically 7-9 digits, but can vary
        if telegram_id < 1000000 or telegram_id > 9999999999:
            return False, "Telegram ID out of valid range"
        
        return True, "Valid Telegram ID"
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input by removing potentially harmful characters"""
        if not text:
            return ""
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Remove control characters except newlines and tabs
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Strip whitespace from ends
        text = text.strip()
        
        return text
    
    @staticmethod
    def validate_file_path(file_path: str) -> Tuple[bool, str]:
        """Validate file path to prevent directory traversal"""
        if not file_path:
            return False, "File path is required"
        
        # Check for directory traversal attempts
        if '..' in file_path or file_path.startswith('/'):
            return False, "Invalid file path"
        
        # Check for allowed file extensions
        allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif']
        if not any(file_path.lower().endswith(ext) for ext in allowed_extensions):
            return False, "Only image files are allowed"
        
        return True, "Valid file path"
    
    @staticmethod
    def validate_pagination_params(page: int, limit: int) -> Tuple[bool, str, int, int]:
        """Validate pagination parameters"""
        try:
            page = max(1, int(page))  # Minimum page is 1
            limit = min(100, max(1, int(limit)))  # Between 1 and 100
            return True, "Valid pagination", page, limit
        except (ValueError, TypeError):
            return False, "Invalid pagination parameters", 1, 10


def validate_user_registration(username: str, password: str, email: Optional[str] = None, 
                              telegram_id: Optional[int] = None) -> Tuple[bool, List[str]]:
    """Validate complete user registration data"""
    errors = []
    
    # Validate username
    is_valid, message = InputValidator.validate_username(username)
    if not is_valid:
        errors.append(message)
    
    # Validate password
    is_valid, message = InputValidator.validate_password(password)
    if not is_valid:
        errors.append(message)
    
    # Validate email (if provided)
    if email:
        is_valid, message = InputValidator.validate_email(email)
        if not is_valid:
            errors.append(message)
    
    # Validate Telegram ID (if provided)
    if telegram_id is not None:
        is_valid, message = InputValidator.validate_telegram_id(telegram_id)
        if not is_valid:
            errors.append(message)
    
    return len(errors) == 0, errors


def validate_qr_creation(content: str, title: Optional[str] = None, 
                         description: Optional[str] = None) -> Tuple[bool, List[str]]:
    """Validate QR code creation data"""
    errors = []
    
    # Validate content
    is_valid, message = InputValidator.validate_qr_content(content)
    if not is_valid:
        errors.append(message)
    
    # Validate title (if provided)
    if title:
        is_valid, message = InputValidator.validate_qr_title(title)
        if not is_valid:
            errors.append(message)
    
    # Validate description (if provided)
    if description:
        is_valid, message = InputValidator.validate_qr_description(description)
        if not is_valid:
            errors.append(message)
    
    return len(errors) == 0, errors


def validate_login_input(username: str, password: str) -> Tuple[bool, List[str]]:
    """Validate login input"""
    errors = []
    
    # Basic validation for login (less strict than registration)
    if not username or len(username) < 1:
        errors.append("Username is required")
    
    if not password or len(password) < 1:
        errors.append("Password is required")
    
    # Sanitize inputs
    username = InputValidator.sanitize_input(username)
    password = InputValidator.sanitize_input(password)
    
    return len(errors) == 0, errors

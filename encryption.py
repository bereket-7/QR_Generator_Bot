from cryptography.fernet import Fernet
import base64
import os
from dotenv import load_dotenv

load_dotenv()


def generate_key():
    """Generate and save a new encryption key"""
    key = Fernet.generate_key()
    with open(".encryption_key", "wb") as key_file:
        key_file.write(key)
    os.environ["ENCRYPTION_KEY"] = key.decode()
    return key


def load_key():
    """Load existing key or generate new one"""
    try:
        with open(".encryption_key", "rb") as key_file:
            return key_file.read()
    except FileNotFoundError:
        return generate_key()


# Initialize cipher
key = load_key()
cipher_suite = Fernet(key)


def encrypt_text(text: str) -> str:
    """Encrypt text with Fernet"""
    return cipher_suite.encrypt(text.encode()).decode()


def decrypt_text(encrypted_text: str) -> str:
    """Decrypt Fernet-encrypted text"""
    return cipher_suite.decrypt(encrypted_text.encode()).decode()

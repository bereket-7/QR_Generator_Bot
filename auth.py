import bcrypt
import jwt
import redis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=True
        )
        self.jwt_secret = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
        self.jwt_algorithm = 'HS256'
        self.token_expiry = timedelta(hours=24)
        
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        try:
            salt = bcrypt.gensalt(rounds=12)
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        except Exception as e:
            logger.error(f"Password hashing error: {e}")
            raise ValueError("Password hashing failed")
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against bcrypt hash"""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'), 
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def generate_token(self, user_id: int, username: str) -> str:
        """Generate JWT token for user"""
        try:
            payload = {
                'user_id': user_id,
                'username': username,
                'exp': datetime.utcnow() + self.token_expiry,
                'iat': datetime.utcnow()
            }
            token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
            
            # Store token in Redis for session management
            session_key = f"session:{user_id}"
            session_data = {
                'token': token,
                'username': username,
                'created_at': datetime.utcnow().isoformat()
            }
            self.redis_client.hset(session_key, mapping=session_data)
            self.redis_client.expire(session_key, self.token_expiry.total_seconds())
            
            return token
        except Exception as e:
            logger.error(f"Token generation error: {e}")
            raise ValueError("Token generation failed")
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Check if token exists in Redis (active session)
            session_key = f"session:{payload['user_id']}"
            stored_token = self.redis_client.hget(session_key, 'token')
            
            if stored_token != token:
                logger.warning(f"Token mismatch for user {payload['user_id']}")
                return None
                
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None
    
    def revoke_token(self, user_id: int) -> bool:
        """Revoke user token/session"""
        try:
            session_key = f"session:{user_id}"
            self.redis_client.delete(session_key)
            return True
        except Exception as e:
            logger.error(f"Token revocation error: {e}")
            return False
    
    def is_rate_limited(self, user_id: int, action: str, limit: int = 5, window: int = 300) -> bool:
        """Check if user is rate limited for specific action"""
        try:
            key = f"rate_limit:{user_id}:{action}"
            current_count = self.redis_client.get(key)
            
            if current_count is None:
                # First request in window
                self.redis_client.setex(key, window, 1)
                return False
            
            if int(current_count) >= limit:
                return True
            
            # Increment counter
            self.redis_client.incr(key)
            return False
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Fail open - allow request if Redis is down
            return False

# Global auth manager instance
auth_manager = AuthManager()

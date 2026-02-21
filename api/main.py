"""
REST API for QR Bot
FastAPI-based REST API with authentication and comprehensive endpoints
"""

from fastapi import FastAPI, HTTPException, Depends, status, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, EmailStr, validator
from typing import Dict, Any, List, Optional, Union
import sqlite3
from datetime import datetime, timedelta
import json
import os
import io
import zipfile
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import get_db_connection
from auth import auth_manager
from dynamic_qr import dynamic_qr_manager
from qr_styling import qr_styler
from analytics import analytics_manager
from batch_qr import batch_qr_generator
from logger_config import logger, security_logger, performance_logger
from app_config import config


# Initialize FastAPI app
app = FastAPI(
    title="QR Bot API",
    description="Advanced QR Code Generator API with analytics and management",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security
security = HTTPBearer()


# Pydantic models
class UserLogin(BaseModel):
    username: str
    password: str
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Username must be between 3 and 50 characters')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v


class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Username must be between 3 and 50 characters')
        return v


class QRCreate(BaseModel):
    content: str
    title: Optional[str] = None
    description: Optional[str] = None
    style_config: Optional[Dict[str, Any]] = {}
    is_dynamic: Optional[bool] = True
    expiration_hours: Optional[int] = None
    
    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError('Content cannot be empty')
        if len(v) > 1000:
            raise ValueError('Content too long (max 1000 characters)')
        return v.strip()


class QRUpdate(BaseModel):
    content: str
    
    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError('Content cannot be empty')
        return v.strip()


class BatchQRCreate(BaseModel):
    data: Union[str, List[Dict[str, Any]]]
    format: str = 'json'
    template_config: Optional[Dict[str, Any]] = {}
    naming_pattern: Optional[str] = None


class APIKeyCreate(BaseModel):
    name: str
    permissions: List[str]
    expires_hours: Optional[int] = None


# Authentication dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Get current authenticated user"""
    
    try:
        token = credentials.credentials
        payload = auth_manager.verify_token(token)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        # Get user from database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, email, is_active 
            FROM users WHERE user_id = ?
        ''', (payload['user_id'],))
        
        user_data = cursor.fetchone()
        conn.close()
        
        if not user_data or user_data[3] != 1:  # is_active
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        return {
            'user_id': user_data[0],
            'username': user_data[1],
            'email': user_data[2]
        }
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


# API Key authentication
async def get_api_key(request: Request):
    """Get API key from request"""
    
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    
    # Validate API key (implementation needed)
    # This would check against database of API keys
    
    return {'api_key': api_key}


# Rate limiting decorator
def rate_limit(limit: str):
    """Rate limiting decorator"""
    def decorator(func):
        return limiter.limit(limit)(func)
    return decorator


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    
    try:
        # Check database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        db_status = "healthy"
        conn.close()
        
        # Check Redis
        redis_status = "healthy"
        try:
            auth_manager.redis_client.ping()
        except:
            redis_status = "unhealthy"
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "database": db_status,
                "redis": redis_status
            }
        }
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


# Authentication endpoints
@app.post("/auth/login", tags=["Authentication"])
@rate_limit("5/minute")
async def login(user_data: UserLogin):
    """User login endpoint"""
    
    try:
        # Authenticate user
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, password_hash, is_active 
            FROM users WHERE username = ?
        ''', (user_data.username,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            security_logger.log_login_attempt(user_data.username, False, "api")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        user_id, password_hash, is_active = result
        
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled"
            )
        
        # Verify password
        if not auth_manager.verify_password(user_data.password, password_hash):
            security_logger.log_login_attempt(user_data.username, False, "api")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Generate token
        token = auth_manager.generate_token(user_id, user_data.username)
        
        security_logger.log_login_attempt(user_data.username, True, "api")
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 3600
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@app.post("/auth/register", tags=["Authentication"])
@rate_limit("3/minute")
async def register(user_data: UserRegister):
    """User registration endpoint"""
    
    try:
        # Check if user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users WHERE username = ?', (user_data.username,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists"
            )
        
        # Hash password and create user
        password_hash = auth_manager.hash_password(user_data.password)
        
        cursor.execute('''
            INSERT INTO users (username, password_hash, email, created_at)
            VALUES (?, ?, ?, ?)
        ''', (
            user_data.username,
            password_hash,
            user_data.email,
            datetime.now().isoformat()
        ))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Generate token
        token = auth_manager.generate_token(user_id, user_data.username)
        
        security_logger.log_user_registration(user_id, user_data.username, None)
        
        return {
            "message": "User created successfully",
            "user_id": user_id,
            "access_token": token,
            "token_type": "bearer"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


# QR Code endpoints
@app.post("/qrcodes", tags=["QR Codes"])
async def create_qr(qr_data: QRCreate, current_user: Dict = Depends(get_current_user)):
    """Create a new QR code"""
    
    try:
        result = dynamic_qr_manager.create_dynamic_qr(
            user_id=current_user['user_id'],
            content=qr_data.content,
            title=qr_data.title,
            description=qr_data.description,
            style_config=qr_data.style_config,
            expiration_hours=qr_data.expiration_hours,
            is_dynamic=qr_data.is_dynamic
        )
        
        if result['success']:
            return {
                "message": "QR code created successfully",
                "qr_id": result['qr_id'],
                "tracking_url": result['tracking_url'],
                "qr_data": result['qr_data']
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['error']
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QR creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create QR code"
        )


@app.get("/qrcodes", tags=["QR Codes"])
async def list_qr_codes(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    current_user: Dict = Depends(get_current_user)
):
    """List user's QR codes"""
    
    try:
        offset = (page - 1) * limit
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query
        query = '''
            SELECT qr_id, title, content, description, created_at, 
                   scan_count, last_scan, is_dynamic
            FROM dynamic_qr_codes 
            WHERE user_id = ?
        '''
        params = [current_user['user_id']]
        
        if search:
            query += ' AND (title LIKE ? OR content LIKE ? OR description LIKE ?)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term])
        
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        qrs = cursor.fetchall()
        
        # Get total count
        count_query = 'SELECT COUNT(*) FROM dynamic_qr_codes WHERE user_id = ?'
        count_params = [current_user['user_id']]
        
        if search:
            count_query += ' AND (title LIKE ? OR content LIKE ? OR description LIKE ?)'
            count_params.extend([f'%{search}%'] * 3)
        
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]
        
        conn.close()
        
        qr_list = []
        for qr in qrs:
            qr_list.append({
                'qr_id': qr[0],
                'title': qr[1],
                'content': qr[2][:100] + '...' if len(qr[2]) > 100 else qr[2],
                'description': qr[3],
                'created_at': qr[4],
                'scan_count': qr[5],
                'last_scan': qr[6],
                'is_dynamic': qr[7]
            })
        
        return {
            "qrcodes": qr_list,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            }
        }
    
    except Exception as e:
        logger.error(f"List QR codes error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list QR codes"
        )


@app.get("/qrcodes/{qr_id}", tags=["QR Codes"])
async def get_qr_code(qr_id: str, current_user: Dict = Depends(get_current_user)):
    """Get QR code details"""
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM dynamic_qr_codes 
            WHERE qr_id = ? AND user_id = ?
        ''', (qr_id, current_user['user_id']))
        
        qr_data = cursor.fetchone()
        conn.close()
        
        if not qr_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR code not found"
            )
        
        return {
            "qr_id": qr_data[0],
            "user_id": qr_data[1],
            "content": qr_data[2],
            "title": qr_data[3],
            "description": qr_data[4],
            "created_at": qr_data[5],
            "is_dynamic": qr_data[6],
            "style_config": json.loads(qr_data[7]) if qr_data[7] else {},
            "expiration": qr_data[8],
            "filepath": qr_data[9],
            "scan_count": qr_data[10],
            "last_scan": qr_data[11]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get QR code error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get QR code"
        )


@app.put("/qrcodes/{qr_id}", tags=["QR Codes"])
async def update_qr_code(
    qr_id: str, 
    qr_update: QRUpdate, 
    current_user: Dict = Depends(get_current_user)
):
    """Update dynamic QR code content"""
    
    try:
        result = dynamic_qr_manager.update_dynamic_content(
            qr_id=qr_id,
            new_content=qr_update.content,
            user_id=current_user['user_id']
        )
        
        if result['success']:
            return {"message": "QR code updated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['error']
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update QR code error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update QR code"
        )


@app.delete("/qrcodes/{qr_id}", tags=["QR Codes"])
async def delete_qr_code(qr_id: str, current_user: Dict = Depends(get_current_user)):
    """Delete QR code"""
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check ownership
        cursor.execute('''
            SELECT user_id FROM dynamic_qr_codes 
            WHERE qr_id = ?
        ''', (qr_id,))
        
        result = cursor.fetchone()
        if not result or result[0] != current_user['user_id']:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR code not found"
            )
        
        # Delete QR code
        cursor.execute('''
            DELETE FROM dynamic_qr_codes 
            WHERE qr_id = ?
        ''', (qr_id,))
        
        conn.commit()
        conn.close()
        
        return {"message": "QR code deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete QR code error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete QR code"
        )


# Analytics endpoints
@app.get("/analytics/dashboard", tags=["Analytics"])
async def get_analytics_dashboard(
    time_range: str = "7d",
    current_user: Dict = Depends(get_current_user)
):
    """Get analytics dashboard data"""
    
    try:
        dashboard_data = analytics_manager.get_dashboard_data(
            user_id=current_user['user_id'],
            time_range=time_range
        )
        
        if dashboard_data['success']:
            return dashboard_data
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=dashboard_data['error']
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analytics dashboard error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get analytics data"
        )


@app.get("/analytics/qrcodes/{qr_id}", tags=["Analytics"])
async def get_qr_analytics(
    qr_id: str, 
    current_user: Dict = Depends(get_current_user)
):
    """Get analytics for specific QR code"""
    
    try:
        analytics_data = analytics_manager.get_qr_analytics(
            qr_id=qr_id,
            user_id=current_user['user_id']
        )
        
        if analytics_data['success']:
            return analytics_data
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=analytics_data['error']
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QR analytics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get QR analytics"
        )


# Batch QR endpoints
@app.post("/batch/qrcodes", tags=["Batch Operations"])
async def create_batch_qr(
    batch_data: BatchQRCreate,
    current_user: Dict = Depends(get_current_user)
):
    """Create QR codes in batch"""
    
    try:
        result = batch_qr_generator.create_batch_qrs(
            user_id=current_user['user_id'],
            data_source=batch_data.data,
            format_type=batch_data.format,
            template_config=batch_data.template_config,
            naming_pattern=batch_data.naming_pattern
        )
        
        if result['success']:
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['error']
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch QR creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create batch QR codes"
        )


# Styling endpoints
@app.get("/styles/templates", tags=["Styling"])
async def get_style_templates():
    """Get available QR styling templates"""
    
    try:
        templates = qr_styler.list_templates()
        return {"templates": templates}
    
    except Exception as e:
        logger.error(f"Get style templates error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get style templates"
        )


@app.get("/styles/templates/{template_id}", tags=["Styling"])
async def get_style_template(template_id: str):
    """Get specific style template"""
    
    try:
        template = qr_styler.get_template(template_id)
        
        if template:
            return {"template": template}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get style template error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get style template"
        )


# QR Tracking endpoint (public)
@app.get("/track/{qr_id}", tags=["Tracking"])
@rate_limit("100/minute")
async def track_qr_scan(
    qr_id: str,
    request: Request
):
    """Track QR code scan (public endpoint)"""
    
    try:
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host
        referrer = request.headers.get("referer")
        
        result = dynamic_qr_manager.track_qr_scan(
            qr_id=qr_id,
            user_agent=user_agent,
            ip_address=ip_address,
            referrer=referrer
        )
        
        if result['success']:
            if result['is_dynamic']:
                # Redirect to actual content
                return JSONResponse(
                    content={"content": result['content']},
                    headers={"X-QR-ID": qr_id}
                )
            else:
                return JSONResponse(
                    content={"message": "Scan tracked successfully"},
                    headers={"X-QR-ID": qr_id}
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR code not found"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QR tracking error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track QR scan"
        )


# User profile endpoint
@app.get("/profile", tags=["User"])
async def get_user_profile(current_user: Dict = Depends(get_current_user)):
    """Get user profile"""
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, email, created_at, last_login
            FROM users WHERE user_id = ?
        ''', (current_user['user_id'],))
        
        user_data = cursor.fetchone()
        
        # Get QR stats
        cursor.execute('''
            SELECT COUNT(*), SUM(scan_count)
            FROM dynamic_qr_codes 
            WHERE user_id = ?
        ''', (current_user['user_id'],))
        
        qr_stats = cursor.fetchone()
        conn.close()
        
        return {
            "user_id": user_data[0],
            "username": user_data[1],
            "email": user_data[2],
            "created_at": user_data[3],
            "last_login": user_data[4],
            "qr_codes_count": qr_stats[0] or 0,
            "total_scans": qr_stats[1] or 0
        }
    
    except Exception as e:
        logger.error(f"Get user profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP exception handler"""
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "timestamp": datetime.now().isoformat()
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    
    logger.error(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "timestamp": datetime.now().isoformat()
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

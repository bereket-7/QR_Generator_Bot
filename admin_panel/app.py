"""
Admin Panel Web Application
Flask-based web interface for QR bot administration
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
import os
from functools import wraps

from database import get_db_connection
from auth import auth_manager
from analytics import analytics_manager
from logger_config import logger, security_logger
from app_config import config


app = Flask(__name__)
app.config['SECRET_KEY'] = config.JWT_SECRET
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'


class AdminUser:
    """Admin user model for Flask-Login"""
    
    def __init__(self, user_data):
        self.id = str(user_data['user_id'])
        self.username = user_data['username']
        self.email = user_data.get('email')
        self.role = user_data.get('role', 'user')
        self.is_authenticated = True
        self.is_active = user_data.get('is_active', 1) == 1
        self.is_anonymous = False
    
    def get_id(self):
        return self.id
    
    def has_role(self, role):
        return self.role == role
    
    def has_permission(self, permission):
        """Check if user has specific permission"""
        permissions = {
            'admin': ['read', 'write', 'delete', 'manage_users', 'view_analytics', 'system_config'],
            'moderator': ['read', 'write', 'delete', 'view_analytics'],
            'analyst': ['read', 'view_analytics'],
            'user': ['read']
        }
        return permission in permissions.get(self.role, [])


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, email, role, is_active 
            FROM users 
            WHERE user_id = ? AND role IN ('admin', 'moderator', 'analyst')
        ''', (int(user_id),))
        
        user_data = cursor.fetchone()
        if user_data:
            return AdminUser(dict(user_data))
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to load user: {e}")
        return None
    finally:
        conn.close()


def admin_required(permission='read'):
    """Decorator to require admin access"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('admin_login'))
            
            if not current_user.has_permission(permission):
                security_logger.log_permission_denied(
                    current_user.id, f"admin_panel_{permission}", "access_denied"
                )
                flash('Access denied. Insufficient permissions.', 'error')
                return redirect(url_for('admin_dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'GET':
        return render_template('admin/login.html')
    
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        flash('Username and password are required', 'error')
        return render_template('admin/login.html')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, password_hash, email, role, is_active
            FROM users 
            WHERE username = ? AND role IN ('admin', 'moderator', 'analyst')
        ''', (username,))
        
        user_data = cursor.fetchone()
        if not user_data:
            flash('Invalid credentials or insufficient permissions', 'error')
            security_logger.log_login_attempt(username, False, request.remote_addr)
            return render_template('admin/login.html')
        
        # Verify password
        if not auth_manager.verify_password(password, user_data[2]):
            flash('Invalid credentials', 'error')
            security_logger.log_login_attempt(username, False, request.remote_addr)
            return render_template('admin/login.html')
        
        # Check if user is active
        if user_data[5] != 1:
            flash('Account is disabled', 'error')
            return render_template('admin/login.html')
        
        # Create user object and login
        user = AdminUser({
            'user_id': user_data[0],
            'username': user_data[1],
            'email': user_data[3],
            'role': user_data[4],
            'is_active': user_data[5]
        })
        
        login_user(user, remember=True)
        session.permanent = True
        
        security_logger.log_login_attempt(username, True, request.remote_addr)
        flash(f'Welcome back, {username}!', 'success')
        
        return redirect(url_for('admin_dashboard'))
        
    except Exception as e:
        logger.error(f"Admin login failed: {e}")
        flash('Login failed. Please try again.', 'error')
        return render_template('admin/login.html')
    finally:
        conn.close()


@app.route('/admin/logout')
@login_required
def admin_logout():
    """Admin logout"""
    username = current_user.username
    logout_user()
    security_logger.log_logout(username, request.remote_addr)
    flash('You have been logged out', 'info')
    return redirect(url_for('admin_login'))


@app.route('/admin')
@login_required
def admin_dashboard():
    """Main admin dashboard"""
    try:
        # Get overview statistics
        stats = get_admin_overview_stats()
        
        # Get recent activity
        recent_activity = get_recent_activity(limit=10)
        
        # Get system health
        system_health = get_system_health()
        
        return render_template('admin/dashboard.html',
                           stats=stats,
                           recent_activity=recent_activity,
                           system_health=system_health)
    
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        flash('Failed to load dashboard', 'error')
        return render_template('admin/dashboard.html',
                           stats={},
                           recent_activity=[],
                           system_health={})


@app.route('/admin/users')
@admin_required('manage_users')
def admin_users():
    """User management page"""
    try:
        page = int(request.args.get('page', 1))
        per_page = 20
        search = request.args.get('search', '')
        
        users = get_users_list(page, per_page, search)
        total_users = get_users_count(search)
        
        return render_template('admin/users.html',
                           users=users,
                           page=page,
                           per_page=per_page,
                           total_users=total_users,
                           search=search)
    
    except Exception as e:
        logger.error(f"Admin users page error: {e}")
        flash('Failed to load users', 'error')
        return render_template('admin/users.html', users=[])


@app.route('/admin/users/<int:user_id>')
@admin_required('manage_users')
def admin_user_detail(user_id):
    """User detail page"""
    try:
        user = get_user_detail(user_id)
        user_analytics = get_user_analytics(user_id)
        user_qrs = get_user_qr_codes(user_id, limit=20)
        
        return render_template('admin/user_detail.html',
                           user=user,
                           analytics=user_analytics,
                           qrs=user_qrs)
    
    except Exception as e:
        logger.error(f"Admin user detail error: {e}")
        flash('Failed to load user details', 'error')
        return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required('manage_users')
def admin_edit_user(user_id):
    """Edit user"""
    if request.method == 'GET':
        user = get_user_detail(user_id)
        return render_template('admin/edit_user.html', user=user)
    
    try:
        # Update user data
        update_data = {
            'username': request.form.get('username'),
            'email': request.form.get('email'),
            'role': request.form.get('role'),
            'is_active': 1 if request.form.get('is_active') else 0
        }
        
        success = update_user(user_id, update_data)
        
        if success:
            flash('User updated successfully', 'success')
            security_logger.log_user_update(current_user.id, user_id, update_data)
        else:
            flash('Failed to update user', 'error')
        
        return redirect(url_for('admin_user_detail', user_id=user_id))
        
    except Exception as e:
        logger.error(f"Admin edit user error: {e}")
        flash('Failed to update user', 'error')
        return redirect(url_for('admin_user_detail', user_id=user_id))


@app.route('/admin/qrcodes')
@admin_required('read')
def admin_qr_codes():
    """QR codes management page"""
    try:
        page = int(request.args.get('page', 1))
        per_page = 20
        search = request.args.get('search', '')
        user_filter = request.args.get('user_filter', '')
        
        qrs = get_qr_codes_list(page, per_page, search, user_filter)
        total_qrs = get_qr_codes_count(search, user_filter)
        
        return render_template('admin/qrcodes.html',
                           qrs=qrs,
                           page=page,
                           per_page=per_page,
                           total_qrs=total_qrs,
                           search=search,
                           user_filter=user_filter)
    
    except Exception as e:
        logger.error(f"Admin QR codes page error: {e}")
        flash('Failed to load QR codes', 'error')
        return render_template('admin/qrcodes.html', qrs=[])


@app.route('/admin/analytics')
@admin_required('view_analytics')
def admin_analytics():
    """Analytics dashboard"""
    try:
        time_range = request.args.get('time_range', '7d')
        
        # Get global analytics
        global_analytics = get_global_analytics(time_range)
        
        # Get top users
        top_users = get_top_users(time_range, limit=10)
        
        # Get top QR codes
        top_qrs = get_top_qr_codes(time_range, limit=10)
        
        return render_template('admin/analytics.html',
                           analytics=global_analytics,
                           top_users=top_users,
                           top_qrs=top_qrs,
                           time_range=time_range)
    
    except Exception as e:
        logger.error(f"Admin analytics page error: {e}")
        flash('Failed to load analytics', 'error')
        return render_template('admin/analytics.html')


@app.route('/admin/security')
@admin_required('manage_users')
def admin_security():
    """Security monitoring page"""
    try:
        # Get security events
        security_events = get_security_events(limit=50)
        
        # Get failed login attempts
        failed_logins = get_failed_login_attempts(limit=20)
        
        # Get locked accounts
        locked_accounts = get_locked_accounts()
        
        return render_template('admin/security.html',
                           security_events=security_events,
                           failed_logins=failed_logins,
                           locked_accounts=locked_accounts)
    
    except Exception as e:
        logger.error(f"Admin security page error: {e}")
        flash('Failed to load security data', 'error')
        return render_template('admin/security.html')


@app.route('/admin/system')
@admin_required('system_config')
def admin_system():
    """System configuration and monitoring"""
    try:
        # Get system stats
        system_stats = get_system_stats()
        
        # Get configuration
        system_config = get_system_config()
        
        return render_template('admin/system.html',
                           system_stats=system_stats,
                           system_config=system_config)
    
    except Exception as e:
        logger.error(f"Admin system page error: {e}")
        flash('Failed to load system data', 'error')
        return render_template('admin/system.html')


# API endpoints for AJAX requests
@app.route('/admin/api/users/<int:user_id>/toggle_status', methods=['POST'])
@admin_required('manage_users')
def toggle_user_status(user_id):
    """Toggle user active status"""
    try:
        success = toggle_user_active_status(user_id)
        
        if success:
            return jsonify({'success': True, 'message': 'User status updated'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update user status'})
    
    except Exception as e:
        logger.error(f"Toggle user status error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/admin/api/qrcodes/<qr_id>/delete', methods=['POST'])
@admin_required('delete')
def delete_qr_code(qr_id):
    """Delete QR code"""
    try:
        success = delete_qr_code_admin(qr_id)
        
        if success:
            return jsonify({'success': True, 'message': 'QR code deleted'})
        else:
            return jsonify({'success': False, 'message': 'Failed to delete QR code'})
    
    except Exception as e:
        logger.error(f"Delete QR code error: {e}")
        return jsonify({'success': False, 'message': str(e)})


# Helper functions
def get_admin_overview_stats() -> Dict[str, Any]:
    """Get overview statistics for admin dashboard"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # User stats
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE created_at > ?', 
                      (datetime.now() - timedelta(days=7)).isoformat())
        new_users_week = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
        active_users = cursor.fetchone()[0]
        
        # QR stats
        cursor.execute('SELECT COUNT(*) FROM dynamic_qr_codes')
        total_qrs = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM dynamic_qr_codes WHERE created_at > ?',
                      (datetime.now() - timedelta(days=7)).isoformat())
        new_qrs_week = cursor.fetchone()[0]
        
        # Scan stats
        cursor.execute('SELECT COUNT(*) FROM qr_scans')
        total_scans = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM qr_scans WHERE scan_time > ?',
                      (datetime.now() - timedelta(days=7)).isoformat())
        scans_week = cursor.fetchone()[0]
        
        return {
            'total_users': total_users,
            'new_users_week': new_users_week,
            'active_users': active_users,
            'total_qrs': total_qrs,
            'new_qrs_week': new_qrs_week,
            'total_scans': total_scans,
            'scans_week': scans_week
        }
    
    finally:
        conn.close()


def get_recent_activity(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent activity for dashboard"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT 'user_created' as activity_type, username, created_at, NULL as details
            FROM users WHERE created_at > ?
            UNION ALL
            SELECT 'qr_created' as activity_type, title, created_at, content as details
            FROM dynamic_qr_codes WHERE created_at > ?
            UNION ALL
            SELECT 'qr_scan' as activity_type, qr_id, scan_time, ip_address as details
            FROM qr_scans WHERE scan_time > ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (
            (datetime.now() - timedelta(days=7)).isoformat(),
            (datetime.now() - timedelta(days=7)).isoformat(),
            (datetime.now() - timedelta(days=7)).isoformat(),
            limit
        ))
        
        activities = []
        for row in cursor.fetchall():
            activities.append({
                'type': row[0],
                'identifier': row[1],
                'timestamp': row[2],
                'details': row[3]
            })
        
        return activities
    
    finally:
        conn.close()


def get_system_health() -> Dict[str, Any]:
    """Get system health information"""
    
    try:
        # Database connectivity
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        db_status = 'healthy' if cursor.fetchone()[0] == 1 else 'unhealthy'
        conn.close()
        
        # Redis connectivity (if available)
        redis_status = 'healthy'
        try:
            auth_manager.redis_client.ping()
        except:
            redis_status = 'unhealthy'
        
        # Disk space
        disk_usage = os.statvfs('.')
        free_space = disk_usage.f_frsize * disk_usage.f_bavail
        total_space = disk_usage.f_frsize * disk_usage.f_blocks
        disk_usage_percent = ((total_space - free_space) / total_space) * 100
        
        return {
            'database': db_status,
            'redis': redis_status,
            'disk_usage': round(disk_usage_percent, 2),
            'free_space_gb': round(free_space / (1024**3), 2),
            'uptime': 'N/A'  # Would need process start time tracking
        }
    
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        return {
            'database': 'error',
            'redis': 'error',
            'disk_usage': 0,
            'free_space_gb': 0,
            'uptime': 'N/A'
        }


# Additional helper functions would be implemented here
# For brevity, I'm showing the main structure


if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates/admin', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)

"""
Dynamic QR Code System
Handles editable QR codes with analytics tracking and advanced features
"""

import qrcode
import io
import base64
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from PIL import Image, ImageDraw, ImageFont
import uuid
import os
from database import get_db_connection, log_qr_scan, update_qr_analytics
from logger_config import logger, audit_logger
from app_config import config


class DynamicQRCode:
    """Advanced QR code with dynamic content and analytics"""
    
    def __init__(self):
        self.qr_cache = {}
        self.analytics_enabled = config.ANALYTICS_ENABLED
        
    def create_dynamic_qr(self, user_id: int, content: str, title: str = None, 
                         description: str = None, style_config: Dict = None,
                         expiration_hours: int = None, is_dynamic: bool = True) -> Dict[str, Any]:
        """Create a dynamic QR code with advanced features"""
        
        try:
            # Generate unique QR ID
            qr_id = str(uuid.uuid4())
            
            # Create QR data payload
            qr_data = {
                'qr_id': qr_id,
                'user_id': user_id,
                'content': content,
                'title': title,
                'description': description,
                'created_at': datetime.now().isoformat(),
                'is_dynamic': is_dynamic,
                'style_config': style_config or {},
                'expiration': None
            }
            
            if expiration_hours:
                qr_data['expiration'] = (datetime.now() + timedelta(hours=expiration_hours)).isoformat()
            
            # Generate QR code image
            qr_image = self._generate_qr_image(qr_data, style_config)
            
            # Save QR code
            filename = f"dynamic_{qr_id}.png"
            filepath = os.path.join('qr_codes', str(user_id), filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            qr_image.save(filepath)
            
            # Save to database
            self._save_dynamic_qr_to_db(qr_data, filepath)
            
            # Log creation
            audit_logger.log_qr_created(user_id, filepath, content[:100])
            
            return {
                'success': True,
                'qr_id': qr_id,
                'filepath': filepath,
                'qr_data': qr_data,
                'tracking_url': f"{config.BASE_URL}/track/{qr_id}"
            }
            
        except Exception as e:
            logger.error(f"Failed to create dynamic QR: {e}")
            return {'success': False, 'error': str(e)}
    
    def _generate_qr_image(self, qr_data: Dict, style_config: Dict) -> Image.Image:
        """Generate styled QR code image"""
        
        # Create base QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        
        # Add data (for dynamic QRs, use tracking URL)
        if qr_data['is_dynamic']:
            qr.add_data(f"{config.BASE_URL}/track/{qr_data['qr_id']}")
        else:
            qr.add_data(qr_data['content'])
        
        qr.make(fit=True)
        
        # Generate base image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Apply custom styling
        if style_config:
            qr_img = self._apply_styling(qr_img, style_config)
        
        return qr_img
    
    def _apply_styling(self, qr_img: Image.Image, style_config: Dict) -> Image.Image:
        """Apply custom styling to QR code"""
        
        # Convert to RGB if needed
        if qr_img.mode != 'RGB':
            qr_img = qr_img.convert('RGB')
        
        # Apply colors
        if 'colors' in style_config:
            colors = style_config['colors']
            qr_img = self._change_qr_colors(qr_img, colors.get('foreground', 'black'), 
                                           colors.get('background', 'white'))
        
        # Add logo
        if 'logo' in style_config:
            logo_path = style_config['logo']
            if os.path.exists(logo_path):
                qr_img = self._add_logo_to_qr(qr_img, logo_path)
        
        # Add rounded corners
        if 'rounded' in style_config and style_config['rounded']:
            qr_img = self._add_rounded_corners(qr_img)
        
        return qr_img
    
    def _change_qr_colors(self, qr_img: Image.Image, fg_color: str, bg_color: str) -> Image.Image:
        """Change QR code colors"""
        
        # Convert to RGB
        qr_img = qr_img.convert('RGB')
        pixels = qr_img.load()
        
        # Convert color names to RGB
        fg_rgb = self._color_to_rgb(fg_color)
        bg_rgb = self._color_to_rgb(bg_color)
        
        # Change colors
        for i in range(qr_img.size[0]):
            for j in range(qr_img.size[1]):
                if pixels[i, j] == (0, 0, 0):  # Black pixels (foreground)
                    pixels[i, j] = fg_rgb
                elif pixels[i, j] == (255, 255, 255):  # White pixels (background)
                    pixels[i, j] = bg_rgb
        
        return qr_img
    
    def _add_logo_to_qr(self, qr_img: Image.Image, logo_path: str) -> Image.Image:
        """Add logo to center of QR code"""
        
        try:
            logo = Image.open(logo_path)
            
            # Calculate logo size (20% of QR size)
            qr_size = qr_img.size[0]
            logo_size = qr_size // 5
            
            # Resize logo
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            
            # Create transparent background for logo area
            logo_pos = ((qr_size - logo_size) // 2, (qr_size - logo_size) // 2)
            
            # Paste logo
            qr_img.paste(logo, logo_pos, logo if logo.mode == 'RGBA' else None)
            
        except Exception as e:
            logger.error(f"Failed to add logo: {e}")
        
        return qr_img
    
    def _add_rounded_corners(self, qr_img: Image.Image, radius: int = 20) -> Image.Image:
        """Add rounded corners to QR code"""
        
        # Create mask for rounded corners
        mask = Image.new('L', qr_img.size, 0)
        draw = ImageDraw.Draw(mask)
        
        # Draw rounded rectangle
        draw.rounded_rectangle([(0, 0), qr_img.size], radius=radius, fill=255)
        
        # Apply mask
        qr_img.putalpha(mask)
        
        return qr_img
    
    def _color_to_rgb(self, color: str) -> tuple:
        """Convert color name/hex to RGB"""
        
        color_map = {
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'yellow': (255, 255, 0),
            'purple': (128, 0, 128),
            'orange': (255, 165, 0),
        }
        
        if color.lower() in color_map:
            return color_map[color.lower()]
        
        # Try hex color
        if color.startswith('#'):
            try:
                hex_color = color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            except:
                pass
        
        # Default to black
        return (0, 0, 0)
    
    def _save_dynamic_qr_to_db(self, qr_data: Dict, filepath: str):
        """Save dynamic QR data to database"""
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO dynamic_qr_codes (
                    qr_id, user_id, content, title, description,
                    created_at, is_dynamic, style_config, expiration,
                    filepath, scan_count, last_scan
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                qr_data['qr_id'],
                qr_data['user_id'],
                qr_data['content'],
                qr_data['title'],
                qr_data['description'],
                qr_data['created_at'],
                qr_data['is_dynamic'],
                json.dumps(qr_data['style_config']),
                qr_data['expiration'],
                filepath,
                0,  # Initial scan count
                None  # Last scan
            ))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save dynamic QR to DB: {e}")
            raise
        finally:
            conn.close()
    
    def update_dynamic_content(self, qr_id: str, new_content: str, user_id: int) -> Dict[str, Any]:
        """Update content of a dynamic QR code"""
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Verify ownership
            cursor.execute('''
                SELECT user_id, content FROM dynamic_qr_codes 
                WHERE qr_id = ? AND is_dynamic = 1
            ''', (qr_id,))
            
            result = cursor.fetchone()
            if not result or result[0] != user_id:
                return {'success': False, 'error': 'QR not found or access denied'}
            
            # Update content
            cursor.execute('''
                UPDATE dynamic_qr_codes 
                SET content = ?, updated_at = ?
                WHERE qr_id = ?
            ''', (new_content, datetime.now().isoformat(), qr_id))
            
            conn.commit()
            
            # Log update
            audit_logger.log_qr_updated(user_id, qr_id, new_content[:100])
            
            return {'success': True, 'message': 'QR content updated successfully'}
            
        except Exception as e:
            logger.error(f"Failed to update dynamic QR: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def get_qr_analytics(self, qr_id: str, user_id: int) -> Dict[str, Any]:
        """Get comprehensive analytics for a QR code"""
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get QR details
            cursor.execute('''
                SELECT * FROM dynamic_qr_codes 
                WHERE qr_id = ? AND user_id = ?
            ''', (qr_id, user_id))
            
            qr_data = cursor.fetchone()
            if not qr_data:
                return {'success': False, 'error': 'QR not found'}
            
            # Get scan analytics
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_scans,
                    COUNT(DISTINCT DATE(scan_time)) as unique_days,
                    MAX(scan_time) as last_scan,
                    MIN(scan_time) as first_scan
                FROM qr_scans 
                WHERE qr_id = ?
            ''', (qr_id,))
            
            scan_data = cursor.fetchone()
            
            # Get geographic data
            cursor.execute('''
                SELECT country, city, COUNT(*) as count
                FROM qr_scans 
                WHERE qr_id = ? AND country IS NOT NULL
                GROUP BY country, city
                ORDER BY count DESC
                LIMIT 10
            ''', (qr_id,))
            
            geo_data = cursor.fetchall()
            
            # Get device data
            cursor.execute('''
                SELECT device_type, browser, COUNT(*) as count
                FROM qr_scans 
                WHERE qr_id = ? AND device_type IS NOT NULL
                GROUP BY device_type, browser
                ORDER BY count DESC
            ''', (qr_id,))
            
            device_data = cursor.fetchall()
            
            return {
                'success': True,
                'qr_details': dict(qr_data),
                'analytics': {
                    'total_scans': scan_data[0] if scan_data else 0,
                    'unique_days': scan_data[1] if scan_data else 0,
                    'last_scan': scan_data[2] if scan_data else None,
                    'first_scan': scan_data[3] if scan_data else None,
                    'geographic': [dict(row) for row in geo_data],
                    'devices': [dict(row) for row in device_data]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get QR analytics: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def track_qr_scan(self, qr_id: str, user_agent: str = None, 
                      ip_address: str = None, referrer: str = None) -> Dict[str, Any]:
        """Track QR code scan with analytics data"""
        
        try:
            # Get QR details
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT content, is_dynamic, user_id FROM dynamic_qr_codes 
                WHERE qr_id = ?
            ''', (qr_id,))
            
            qr_data = cursor.fetchone()
            if not qr_data:
                return {'success': False, 'error': 'QR not found'}
            
            content, is_dynamic, owner_id = qr_data
            
            # Parse user agent
            device_info = self._parse_user_agent(user_agent) if user_agent else {}
            
            # Get location info (simplified)
            location_info = self._get_location_info(ip_address) if ip_address else {}
            
            # Log scan
            cursor.execute('''
                INSERT INTO qr_scans (
                    qr_id, scan_time, user_agent, ip_address, referrer,
                    device_type, browser, os, country, city
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                qr_id, datetime.now().isoformat(), user_agent, ip_address, referrer,
                device_info.get('device_type'),
                device_info.get('browser'),
                device_info.get('os'),
                location_info.get('country'),
                location_info.get('city')
            ))
            
            # Update QR scan count
            cursor.execute('''
                UPDATE dynamic_qr_codes 
                SET scan_count = scan_count + 1, last_scan = ?
                WHERE qr_id = ?
            ''', (datetime.now().isoformat(), qr_id))
            
            conn.commit()
            
            # Log analytics
            audit_logger.log_qr_scan(owner_id, qr_id, ip_address)
            
            return {
                'success': True,
                'content': content,
                'is_dynamic': is_dynamic,
                'qr_id': qr_id
            }
            
        except Exception as e:
            logger.error(f"Failed to track QR scan: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def _parse_user_agent(self, user_agent: str) -> Dict[str, str]:
        """Parse user agent string for device info"""
        
        device_info = {}
        ua_lower = user_agent.lower()
        
        # Detect device type
        if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
            device_info['device_type'] = 'mobile'
        elif 'tablet' in ua_lower or 'ipad' in ua_lower:
            device_info['device_type'] = 'tablet'
        else:
            device_info['device_type'] = 'desktop'
        
        # Detect browser
        if 'chrome' in ua_lower:
            device_info['browser'] = 'Chrome'
        elif 'firefox' in ua_lower:
            device_info['browser'] = 'Firefox'
        elif 'safari' in ua_lower:
            device_info['browser'] = 'Safari'
        elif 'edge' in ua_lower:
            device_info['browser'] = 'Edge'
        else:
            device_info['browser'] = 'Other'
        
        # Detect OS
        if 'windows' in ua_lower:
            device_info['os'] = 'Windows'
        elif 'mac' in ua_lower:
            device_info['os'] = 'macOS'
        elif 'linux' in ua_lower:
            device_info['os'] = 'Linux'
        elif 'android' in ua_lower:
            device_info['os'] = 'Android'
        elif 'ios' in ua_lower or 'iphone' in ua_lower:
            device_info['os'] = 'iOS'
        else:
            device_info['os'] = 'Other'
        
        return device_info
    
    def _get_location_info(self, ip_address: str) -> Dict[str, str]:
        """Get location info from IP address (simplified)"""
        
        # This is a placeholder - in production, you'd use a real GeoIP service
        # like MaxMind GeoIP2, ipinfo.io, or similar
        
        location_info = {}
        
        # For demo purposes, return some sample data
        if ip_address:
            # In production, integrate with real GeoIP service
            location_info = {
                'country': 'Unknown',
                'city': 'Unknown'
            }
        
        return location_info


# Global instance
dynamic_qr_manager = DynamicQRCode()

"""
Analytics System for QR Bot
Comprehensive analytics tracking, reporting, and visualization
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from database import get_db_connection
from logger_config import logger, performance_logger
import statistics
from collections import defaultdict, Counter


class QRAnalytics:
    """Comprehensive analytics system for QR codes and user behavior"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timeout = 300  # 5 minutes
    
    def get_dashboard_data(self, user_id: int, time_range: str = '7d') -> Dict[str, Any]:
        """Get comprehensive dashboard data for a user"""
        
        try:
            # Calculate date range
            end_date = datetime.now()
            if time_range == '1d':
                start_date = end_date - timedelta(days=1)
            elif time_range == '7d':
                start_date = end_date - timedelta(days=7)
            elif time_range == '30d':
                start_date = end_date - timedelta(days=30)
            elif time_range == '90d':
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=7)
            
            # Get overview statistics
            overview = self._get_overview_stats(user_id, start_date, end_date)
            
            # Get QR performance data
            qr_performance = self._get_qr_performance(user_id, start_date, end_date)
            
            # Get geographic data
            geographic = self._get_geographic_data(user_id, start_date, end_date)
            
            # Get device analytics
            device_analytics = self._get_device_analytics(user_id, start_date, end_date)
            
            # Get time-based analytics
            time_analytics = self._get_time_analytics(user_id, start_date, end_date)
            
            # Get top performing QRs
            top_qrs = self._get_top_qrs(user_id, start_date, end_date, limit=10)
            
            return {
                'success': True,
                'time_range': time_range,
                'overview': overview,
                'qr_performance': qr_performance,
                'geographic': geographic,
                'device_analytics': device_analytics,
                'time_analytics': time_analytics,
                'top_qrs': top_qrs,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_overview_stats(self, user_id: int, start_date: datetime, 
                          end_date: datetime) -> Dict[str, Any]:
        """Get overview statistics"""
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Total QR codes
            cursor.execute('''
                SELECT COUNT(*) FROM dynamic_qr_codes 
                WHERE user_id = ? AND created_at BETWEEN ? AND ?
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            total_qrs = cursor.fetchone()[0]
            
            # Total scans
            cursor.execute('''
                SELECT COUNT(*) FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            total_scans = cursor.fetchone()[0]
            
            # Unique QRs scanned
            cursor.execute('''
                SELECT COUNT(DISTINCT s.qr_id) FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            unique_qrs_scanned = cursor.fetchone()[0]
            
            # Average scans per QR
            avg_scans = total_scans / total_qrs if total_qrs > 0 else 0
            
            # Growth metrics (compare with previous period)
            previous_start = start_date - (end_date - start_date)
            previous_end = start_date
            
            cursor.execute('''
                SELECT COUNT(*) FROM dynamic_qr_codes 
                WHERE user_id = ? AND created_at BETWEEN ? AND ?
            ''', (user_id, previous_start.isoformat(), previous_end.isoformat()))
            previous_qrs = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
            ''', (user_id, previous_start.isoformat(), previous_end.isoformat()))
            previous_scans = cursor.fetchone()[0]
            
            # Calculate growth rates
            qr_growth = self._calculate_growth_rate(total_qrs, previous_qrs)
            scan_growth = self._calculate_growth_rate(total_scans, previous_scans)
            
            return {
                'total_qr_codes': total_qrs,
                'total_scans': total_scans,
                'unique_qrs_scanned': unique_qrs_scanned,
                'average_scans_per_qr': round(avg_scans, 2),
                'qr_growth_rate': qr_growth,
                'scan_growth_rate': scan_growth,
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat()
            }
            
        finally:
            conn.close()
    
    def _get_qr_performance(self, user_id: int, start_date: datetime, 
                           end_date: datetime) -> List[Dict[str, Any]]:
        """Get individual QR performance data"""
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT 
                    q.qr_id,
                    q.title,
                    q.content,
                    q.created_at,
                    q.scan_count,
                    COUNT(s.scan_time) as period_scans,
                    MAX(s.scan_time) as last_scan
                FROM dynamic_qr_codes q
                LEFT JOIN qr_scans s ON q.qr_id = s.qr_id 
                    AND s.scan_time BETWEEN ? AND ?
                WHERE q.user_id = ?
                GROUP BY q.qr_id
                ORDER BY period_scans DESC
            ''', (start_date.isoformat(), end_date.isoformat(), user_id))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'qr_id': row[0],
                    'title': row[1] or 'Untitled',
                    'content': row[2][:50] + '...' if len(row[2]) > 50 else row[2],
                    'created_at': row[3],
                    'total_scans': row[4],
                    'period_scans': row[5],
                    'last_scan': row[6],
                    'performance_score': self._calculate_performance_score(row[5], row[3])
                })
            
            return results
            
        finally:
            conn.close()
    
    def _get_geographic_data(self, user_id: int, start_date: datetime, 
                           end_date: datetime) -> Dict[str, Any]:
        """Get geographic distribution of scans"""
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Country distribution
            cursor.execute('''
                SELECT 
                    COALESCE(country, 'Unknown') as country,
                    COUNT(*) as scans,
                    COUNT(DISTINCT s.qr_id) as unique_qrs
                FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
                GROUP BY country
                ORDER BY scans DESC
                LIMIT 10
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            
            country_data = []
            for row in cursor.fetchall():
                country_data.append({
                    'country': row[0],
                    'scans': row[1],
                    'unique_qrs': row[2],
                    'percentage': 0  # Will be calculated
                })
            
            # Calculate percentages
            total_scans = sum(item['scans'] for item in country_data)
            for item in country_data:
                item['percentage'] = round((item['scans'] / total_scans * 100), 2) if total_scans > 0 else 0
            
            # City distribution (top cities)
            cursor.execute('''
                SELECT 
                    COALESCE(city, 'Unknown') as city,
                    COALESCE(country, 'Unknown') as country,
                    COUNT(*) as scans
                FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
                GROUP BY city, country
                ORDER BY scans DESC
                LIMIT 20
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            
            city_data = []
            for row in cursor.fetchall():
                city_data.append({
                    'city': row[0],
                    'country': row[1],
                    'scans': row[2]
                })
            
            return {
                'countries': country_data,
                'cities': city_data,
                'total_countries': len(country_data),
                'total_cities': len(city_data)
            }
            
        finally:
            conn.close()
    
    def _get_device_analytics(self, user_id: int, start_date: datetime, 
                            end_date: datetime) -> Dict[str, Any]:
        """Get device and browser analytics"""
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Device type distribution
            cursor.execute('''
                SELECT 
                    COALESCE(device_type, 'Unknown') as device_type,
                    COUNT(*) as scans,
                    COUNT(DISTINCT s.qr_id) as unique_qrs
                FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
                GROUP BY device_type
                ORDER BY scans DESC
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            
            device_data = []
            for row in cursor.fetchall():
                device_data.append({
                    'device_type': row[0],
                    'scans': row[1],
                    'unique_qrs': row[2]
                })
            
            # Browser distribution
            cursor.execute('''
                SELECT 
                    COALESCE(browser, 'Unknown') as browser,
                    COUNT(*) as scans
                FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
                GROUP BY browser
                ORDER BY scans DESC
                LIMIT 10
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            
            browser_data = []
            for row in cursor.fetchall():
                browser_data.append({
                    'browser': row[0],
                    'scans': row[1]
                })
            
            # OS distribution
            cursor.execute('''
                SELECT 
                    COALESCE(os, 'Unknown') as os,
                    COUNT(*) as scans
                FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
                GROUP BY os
                ORDER BY scans DESC
                LIMIT 10
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            
            os_data = []
            for row in cursor.fetchall():
                os_data.append({
                    'os': row[0],
                    'scans': row[1]
                })
            
            return {
                'devices': device_data,
                'browsers': browser_data,
                'operating_systems': os_data
            }
            
        finally:
            conn.close()
    
    def _get_time_analytics(self, user_id: int, start_date: datetime, 
                          end_date: datetime) -> Dict[str, Any]:
        """Get time-based analytics (hourly, daily patterns)"""
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Hourly distribution
            cursor.execute('''
                SELECT 
                    CAST(strftime('%H', scan_time) AS INTEGER) as hour,
                    COUNT(*) as scans
                FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
                GROUP BY hour
                ORDER BY hour
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            
            hourly_data = []
            for row in cursor.fetchall():
                hourly_data.append({
                    'hour': row[0],
                    'scans': row[1]
                })
            
            # Daily distribution
            cursor.execute('''
                SELECT 
                    DATE(scan_time) as date,
                    COUNT(*) as scans,
                    COUNT(DISTINCT s.qr_id) as unique_qrs
                FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
                GROUP BY DATE(scan_time)
                ORDER BY date
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            
            daily_data = []
            for row in cursor.fetchall():
                daily_data.append({
                    'date': row[0],
                    'scans': row[1],
                    'unique_qrs': row[2]
                })
            
            # Day of week distribution
            cursor.execute('''
                SELECT 
                    CAST(strftime('%w', scan_time) AS INTEGER) as day_of_week,
                    COUNT(*) as scans
                FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time BETWEEN ? AND ?
                GROUP BY day_of_week
                ORDER BY day_of_week
            ''', (user_id, start_date.isoformat(), end_date.isoformat()))
            
            dow_data = []
            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            for row in cursor.fetchall():
                dow_data.append({
                    'day_of_week': row[0],
                    'day_name': day_names[row[0]],
                    'scans': row[1]
                })
            
            return {
                'hourly_distribution': hourly_data,
                'daily_distribution': daily_data,
                'day_of_week_distribution': dow_data
            }
            
        finally:
            conn.close()
    
    def _get_top_qrs(self, user_id: int, start_date: datetime, 
                    end_date: datetime, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top performing QR codes"""
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT 
                    q.qr_id,
                    q.title,
                    q.content,
                    q.created_at,
                    COUNT(s.scan_time) as scans,
                    COUNT(DISTINCT DATE(s.scan_time)) as active_days,
                    MAX(s.scan_time) as last_scan,
                    AVG(
                        CASE 
                            WHEN device_type = 'mobile' THEN 1.2
                            WHEN device_type = 'tablet' THEN 1.1
                            ELSE 1.0
                        END
                    ) as engagement_score
                FROM dynamic_qr_codes q
                LEFT JOIN qr_scans s ON q.qr_id = s.qr_id 
                    AND s.scan_time BETWEEN ? AND ?
                WHERE q.user_id = ?
                GROUP BY q.qr_id
                HAVING scans > 0
                ORDER BY scans DESC, engagement_score DESC
                LIMIT ?
            ''', (start_date.isoformat(), end_date.isoformat(), user_id, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'qr_id': row[0],
                    'title': row[1] or 'Untitled',
                    'content': row[2][:50] + '...' if len(row[2]) > 50 else row[2],
                    'created_at': row[3],
                    'scans': row[4],
                    'active_days': row[5],
                    'last_scan': row[6],
                    'engagement_score': round(row[7], 2) if row[7] else 0,
                    'trend': self._calculate_trend(row[0], start_date, end_date)
                })
            
            return results
            
        finally:
            conn.close()
    
    def _calculate_growth_rate(self, current: int, previous: int) -> float:
        """Calculate growth rate percentage"""
        
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        
        return round(((current - previous) / previous) * 100, 2)
    
    def _calculate_performance_score(self, scans: int, created_at: str) -> float:
        """Calculate performance score for a QR code"""
        
        if scans == 0:
            return 0.0
        
        # Age of QR in days
        age_days = (datetime.now() - datetime.fromisoformat(created_at)).days
        if age_days == 0:
            age_days = 1
        
        # Scans per day
        scans_per_day = scans / age_days
        
        # Performance score (0-100)
        # Base score on scans per day with logarithmic scaling
        score = min(100, (scans_per_day * 10) ** 0.7 * 20)
        
        return round(score, 2)
    
    def _calculate_trend(self, qr_id: str, start_date: datetime, 
                        end_date: datetime) -> str:
        """Calculate trend for a QR code"""
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Split period in half
            mid_date = start_date + (end_date - start_date) / 2
            
            # First half scans
            cursor.execute('''
                SELECT COUNT(*) FROM qr_scans 
                WHERE qr_id = ? AND scan_time BETWEEN ? AND ?
            ''', (qr_id, start_date.isoformat(), mid_date.isoformat()))
            first_half = cursor.fetchone()[0]
            
            # Second half scans
            cursor.execute('''
                SELECT COUNT(*) FROM qr_scans 
                WHERE qr_id = ? AND scan_time BETWEEN ? AND ?
            ''', (qr_id, mid_date.isoformat(), end_date.isoformat()))
            second_half = cursor.fetchone()[0]
            
            if first_half == 0:
                return 'stable' if second_half == 0 else 'up'
            
            ratio = second_half / first_half
            
            if ratio > 1.2:
                return 'up'
            elif ratio < 0.8:
                return 'down'
            else:
                return 'stable'
                
        finally:
            conn.close()
    
    def get_real_time_data(self, user_id: int) -> Dict[str, Any]:
        """Get real-time analytics data"""
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Recent scans (last hour)
            one_hour_ago = datetime.now() - timedelta(hours=1)
            cursor.execute('''
                SELECT COUNT(*) FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time > ?
            ''', (user_id, one_hour_ago.isoformat()))
            recent_scans = cursor.fetchone()[0]
            
            # Active QRs (scanned in last 24 hours)
            one_day_ago = datetime.now() - timedelta(days=1)
            cursor.execute('''
                SELECT COUNT(DISTINCT s.qr_id) FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time > ?
            ''', (user_id, one_day_ago.isoformat()))
            active_qrs = cursor.fetchone()[0]
            
            # Top locations in last hour
            cursor.execute('''
                SELECT COALESCE(country, 'Unknown') as country, COUNT(*) as scans
                FROM qr_scans s
                JOIN dynamic_qr_codes q ON s.qr_id = q.qr_id
                WHERE q.user_id = ? AND s.scan_time > ?
                GROUP BY country
                ORDER BY scans DESC
                LIMIT 5
            ''', (user_id, one_hour_ago.isoformat()))
            
            recent_locations = []
            for row in cursor.fetchall():
                recent_locations.append({
                    'country': row[0],
                    'scans': row[1]
                })
            
            return {
                'success': True,
                'recent_scans_hour': recent_scans,
                'active_qrs_24h': active_qrs,
                'recent_locations': recent_locations,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get real-time data: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def export_analytics(self, user_id: int, format: str = 'json', 
                        time_range: str = '30d') -> Dict[str, Any]:
        """Export analytics data in various formats"""
        
        try:
            # Get dashboard data
            dashboard_data = self.get_dashboard_data(user_id, time_range)
            
            if not dashboard_data.get('success'):
                return dashboard_data
            
            if format == 'json':
                return {
                    'success': True,
                    'data': dashboard_data,
                    'format': 'json'
                }
            
            elif format == 'csv':
                # Convert to CSV format
                csv_data = self._convert_to_csv(dashboard_data)
                return {
                    'success': True,
                    'data': csv_data,
                    'format': 'csv'
                }
            
            else:
                return {'success': False, 'error': 'Unsupported format'}
                
        except Exception as e:
            logger.error(f"Failed to export analytics: {e}")
            return {'success': False, 'error': str(e)}
    
    def _convert_to_csv(self, data: Dict[str, Any]) -> str:
        """Convert analytics data to CSV format"""
        
        csv_lines = []
        
        # Overview data
        overview = data.get('overview', {})
        csv_lines.append('Metric,Value')
        csv_lines.append(f"Total QR Codes,{overview.get('total_qr_codes', 0)}")
        csv_lines.append(f"Total Scans,{overview.get('total_scans', 0)}")
        csv_lines.append(f"Unique QRs Scanned,{overview.get('unique_qrs_scanned', 0)}")
        csv_lines.append(f"Average Scans per QR,{overview.get('average_scans_per_qr', 0)}")
        csv_lines.append("")
        
        # QR performance data
        csv_lines.append('QR Performance')
        csv_lines.append('QR ID,Title,Content,Created At,Total Scans,Period Scans,Last Scan')
        
        for qr in data.get('qr_performance', []):
            csv_lines.append(f"{qr['qr_id']},{qr['title']},{qr['content']},{qr['created_at']},{qr['total_scans']},{qr['period_scans']},{qr['last_scan']}")
        
        return '\n'.join(csv_lines)


# Global instance
analytics_manager = QRAnalytics()

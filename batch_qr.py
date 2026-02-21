"""
Batch QR Generation System
Handles bulk QR code generation from various data sources
"""

import csv
import json
import io
import os
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import zipfile
import tempfile
from database import get_db_connection
from dynamic_qr import dynamic_qr_manager
from qr_styling import qr_styler
from logger_config import logger, audit_logger, performance_logger
from app_config import config


class BatchQRGenerator:
    """Advanced batch QR generation with multiple input formats"""
    
    def __init__(self):
        self.supported_formats = ['csv', 'json', 'xlsx', 'txt']
        self.max_batch_size = config.MAX_BATCH_SIZE if hasattr(config, 'MAX_BATCH_SIZE') else 1000
    
    def create_batch_qrs(self, user_id: int, data_source: Union[str, bytes], 
                         format_type: str, template_config: Dict[str, Any] = None,
                         naming_pattern: str = None) -> Dict[str, Any]:
        """Create QR codes in batch from various data sources"""
        
        try:
            # Validate batch size
            if format_type == 'csv':
                data = self._parse_csv(data_source)
            elif format_type == 'json':
                data = self._parse_json(data_source)
            elif format_type == 'txt':
                data = self._parse_txt(data_source)
            else:
                return {'success': False, 'error': 'Unsupported format'}
            
            if len(data) > self.max_batch_size:
                return {'success': False, 'error': f'Batch size exceeds limit of {self.max_batch_size}'}
            
            # Process batch
            batch_id = self._generate_batch_id()
            results = []
            failed_items = []
            
            for index, item in enumerate(data):
                try:
                    # Extract content and metadata
                    content = self._extract_content(item, format_type)
                    title = self._extract_title(item, format_type, index, naming_pattern)
                    description = self._extract_description(item, format_type)
                    
                    # Create QR code
                    qr_result = dynamic_qr_manager.create_dynamic_qr(
                        user_id=user_id,
                        content=content,
                        title=title,
                        description=description,
                        style_config=template_config.get('style', {}) if template_config else {},
                        expiration_hours=template_config.get('expiration_hours') if template_config else None,
                        is_dynamic=template_config.get('is_dynamic', True) if template_config else True
                    )
                    
                    if qr_result['success']:
                        results.append({
                            'index': index,
                            'qr_id': qr_result['qr_id'],
                            'title': title,
                            'content': content,
                            'filepath': qr_result['filepath']
                        })
                    else:
                        failed_items.append({
                            'index': index,
                            'content': content,
                            'error': qr_result['error']
                        })
                        
                except Exception as e:
                    failed_items.append({
                        'index': index,
                        'content': str(item),
                        'error': str(e)
                    })
            
            # Save batch record
            batch_record = self._save_batch_record(user_id, batch_id, data, results, failed_items)
            
            # Create downloadable package if requested
            package_path = None
            if template_config and template_config.get('create_package', False):
                package_path = self._create_download_package(batch_id, results)
            
            # Log batch creation
            audit_logger.log_batch_qr_created(user_id, batch_id, len(results), len(failed_items))
            
            return {
                'success': True,
                'batch_id': batch_id,
                'total_processed': len(data),
                'successful': len(results),
                'failed': len(failed_items),
                'results': results,
                'failed_items': failed_items,
                'package_path': package_path,
                'batch_record': batch_record
            }
            
        except Exception as e:
            logger.error(f"Batch QR generation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _parse_csv(self, data_source: Union[str, bytes]) -> List[Dict[str, Any]]:
        """Parse CSV data source"""
        
        if isinstance(data_source, bytes):
            data_source = data_source.decode('utf-8')
        
        reader = csv.DictReader(io.StringIO(data_source))
        return list(reader)
    
    def _parse_json(self, data_source: Union[str, bytes]) -> List[Dict[str, Any]]:
        """Parse JSON data source"""
        
        if isinstance(data_source, bytes):
            data_source = data_source.decode('utf-8')
        
        data = json.loads(data_source)
        
        # Handle different JSON structures
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and 'items' in data:
            return data['items']
        elif isinstance(data, dict) and 'data' in data:
            return data['data']
        else:
            return [data]
    
    def _parse_txt(self, data_source: Union[str, bytes]) -> List[Dict[str, Any]]:
        """Parse text data source (one item per line)"""
        
        if isinstance(data_source, bytes):
            data_source = data_source.decode('utf-8')
        
        lines = data_source.strip().split('\n')
        return [{'content': line.strip()} for line in lines if line.strip()]
    
    def _extract_content(self, item: Dict[str, Any], format_type: str) -> str:
        """Extract QR content from data item"""
        
        # Try common field names
        content_fields = ['content', 'url', 'text', 'data', 'value', 'link', 'address']
        
        for field in content_fields:
            if field in item and item[field]:
                return str(item[field]).strip()
        
        # Fallback to first non-empty field
        for value in item.values():
            if value and str(value).strip():
                return str(value).strip()
        
        return 'No content'
    
    def _extract_title(self, item: Dict[str, Any], format_type: str, 
                      index: int, naming_pattern: str = None) -> str:
        """Extract or generate title for QR code"""
        
        # Try common title fields
        title_fields = ['title', 'name', 'label', 'subject', 'header']
        
        for field in title_fields:
            if field in item and item[field]:
                return str(item[field]).strip()
        
        # Use naming pattern if provided
        if naming_pattern:
            return self._apply_naming_pattern(naming_pattern, item, index)
        
        # Generate default title
        content = self._extract_content(item, format_type)
        if len(content) > 30:
            return content[:27] + '...'
        return content
    
    def _extract_description(self, item: Dict[str, Any], format_type: str) -> str:
        """Extract description from data item"""
        
        # Try common description fields
        desc_fields = ['description', 'desc', 'details', 'info', 'notes', 'comment']
        
        for field in desc_fields:
            if field in item and item[field]:
                return str(item[field]).strip()
        
        return ''
    
    def _apply_naming_pattern(self, pattern: str, item: Dict[str, Any], index: int) -> str:
        """Apply naming pattern to generate title"""
        
        # Replace placeholders
        title = pattern.replace('{index}', str(index + 1))
        title = title.replace('{content}', self._extract_content(item, 'json'))
        
        # Replace field placeholders
        for field, value in item.items():
            placeholder = f'{{{field}}}'
            if placeholder in title:
                title = title.replace(placeholder, str(value))
        
        return title
    
    def _generate_batch_id(self) -> str:
        """Generate unique batch ID"""
        
        return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(datetime.now()) % 10000}"
    
    def _save_batch_record(self, user_id: int, batch_id: str, original_data: List[Dict],
                          results: List[Dict], failed_items: List[Dict]) -> Dict[str, Any]:
        """Save batch record to database"""
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Create batch record
            cursor.execute('''
                INSERT INTO batch_qr_records (
                    batch_id, user_id, total_items, successful_count,
                    failed_count, created_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                batch_id, user_id, len(original_data), len(results),
                len(failed_items), datetime.now().isoformat(), 'completed'
            ))
            
            conn.commit()
            
            return {
                'batch_id': batch_id,
                'user_id': user_id,
                'total_items': len(original_data),
                'successful_count': len(results),
                'failed_count': len(failed_items),
                'created_at': datetime.now().isoformat(),
                'status': 'completed'
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save batch record: {e}")
            raise
        finally:
            conn.close()
    
    def _create_download_package(self, batch_id: str, results: List[Dict]) -> str:
        """Create downloadable ZIP package of all QR codes"""
        
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp()
            package_path = os.path.join(temp_dir, f"{batch_id}.zip")
            
            with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add QR images
                for result in results:
                    qr_path = result['filepath']
                    if os.path.exists(qr_path):
                        zipf.write(qr_path, os.path.basename(qr_path))
                
                # Add metadata file
                metadata = {
                    'batch_id': batch_id,
                    'created_at': datetime.now().isoformat(),
                    'total_qrs': len(results),
                    'qr_codes': results
                }
                
                metadata_path = os.path.join(temp_dir, 'metadata.json')
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                zipf.write(metadata_path, 'metadata.json')
            
            return package_path
            
        except Exception as e:
            logger.error(f"Failed to create download package: {e}")
            return None
    
    def get_batch_status(self, user_id: int, batch_id: str) -> Dict[str, Any]:
        """Get status of a batch generation job"""
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM batch_qr_records 
                WHERE batch_id = ? AND user_id = ?
            ''', (batch_id, user_id))
            
            record = cursor.fetchone()
            if not record:
                return {'success': False, 'error': 'Batch not found'}
            
            return {
                'success': True,
                'batch_record': dict(record)
            }
            
        except Exception as e:
            logger.error(f"Failed to get batch status: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def list_user_batches(self, user_id: int, limit: int = 20) -> Dict[str, Any]:
        """List all batch jobs for a user"""
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM batch_qr_records 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            
            batches = []
            for row in cursor.fetchall():
                batches.append(dict(row))
            
            return {
                'success': True,
                'batches': batches,
                'total': len(batches)
            }
            
        except Exception as e:
            logger.error(f"Failed to list user batches: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def create_qr_template(self, user_id: int, name: str, description: str,
                          style_config: Dict[str, Any], naming_pattern: str = None) -> Dict[str, Any]:
        """Create a reusable QR template"""
        
        try:
            template_id = f"template_{user_id}_{hash(name) % 10000}"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO qr_templates (
                    template_id, user_id, name, description,
                    style_config, naming_pattern, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                template_id, user_id, name, description,
                json.dumps(style_config), naming_pattern, datetime.now().isoformat()
            ))
            
            conn.commit()
            
            return {
                'success': True,
                'template_id': template_id,
                'message': 'Template created successfully'
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create QR template: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def get_user_templates(self, user_id: int) -> Dict[str, Any]:
        """Get all templates for a user"""
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM qr_templates 
                WHERE user_id = ? OR user_id IS NULL
                ORDER BY user_id DESC, created_at DESC
            ''', (user_id,))
            
            templates = []
            for row in cursor.fetchall():
                template = dict(row)
                template['style_config'] = json.loads(template['style_config'])
                templates.append(template)
            
            return {
                'success': True,
                'templates': templates,
                'total': len(templates)
            }
            
        except Exception as e:
            logger.error(f"Failed to get user templates: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def validate_batch_data(self, data_source: Union[str, bytes], 
                           format_type: str) -> Dict[str, Any]:
        """Validate batch data before processing"""
        
        try:
            if format_type not in self.supported_formats:
                return {'success': False, 'error': f'Unsupported format: {format_type}'}
            
            # Parse data
            if format_type == 'csv':
                data = self._parse_csv(data_source)
            elif format_type == 'json':
                data = self._parse_json(data_source)
            elif format_type == 'txt':
                data = self._parse_txt(data_source)
            
            # Validate data structure
            if not data:
                return {'success': False, 'error': 'No data found in source'}
            
            if len(data) > self.max_batch_size:
                return {'success': False, 'error': f'Data size ({len(data)}) exceeds limit ({self.max_batch_size})'}
            
            # Validate content extraction
            valid_items = 0
            for item in data:
                content = self._extract_content(item, format_type)
                if content and content != 'No content':
                    valid_items += 1
            
            if valid_items == 0:
                return {'success': False, 'error': 'No valid content found in data'}
            
            return {
                'success': True,
                'total_items': len(data),
                'valid_items': valid_items,
                'invalid_items': len(data) - valid_items,
                'sample_data': data[:3]  # First 3 items for preview
            }
            
        except Exception as e:
            logger.error(f"Batch data validation failed: {e}")
            return {'success': False, 'error': str(e)}


# Global instance
batch_qr_generator = BatchQRGenerator()

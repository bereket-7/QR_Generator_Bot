"""
Cloud Storage Integration
Supports AWS S3, Google Drive, and other cloud storage providers
"""

import os
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from typing import Dict, Any, List, Optional, BinaryIO
import io
from datetime import datetime, timedelta
from logger_config import logger, performance_logger
from app_config import config


class CloudStorageManager:
    """Manages cloud storage operations across multiple providers"""
    
    def __init__(self):
        self.providers = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available cloud storage providers"""
        
        # Initialize AWS S3
        if hasattr(config, 'AWS_ACCESS_KEY_ID') and hasattr(config, 'AWS_SECRET_ACCESS_KEY'):
            try:
                self.providers['s3'] = S3StorageProvider()
                logger.info("AWS S3 provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize S3 provider: {e}")
        
        # Initialize Google Drive
        if hasattr(config, 'GOOGLE_CREDENTIALS_PATH'):
            try:
                self.providers['gdrive'] = GoogleDriveProvider()
                logger.info("Google Drive provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Google Drive provider: {e}")
    
    def upload_file(self, file_path: str, provider: str = 's3', 
                   destination_path: str = None, metadata: Dict = None) -> Dict[str, Any]:
        """Upload file to specified cloud storage provider"""
        
        if provider not in self.providers:
            return {'success': False, 'error': f'Provider {provider} not available'}
        
        try:
            return self.providers[provider].upload_file(file_path, destination_path, metadata)
        except Exception as e:
            logger.error(f"Cloud upload failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def download_file(self, cloud_path: str, provider: str = 's3',
                     local_path: str = None) -> Dict[str, Any]:
        """Download file from cloud storage"""
        
        if provider not in self.providers:
            return {'success': False, 'error': f'Provider {provider} not available'}
        
        try:
            return self.providers[provider].download_file(cloud_path, local_path)
        except Exception as e:
            logger.error(f"Cloud download failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def list_files(self, provider: str = 's3', prefix: str = None,
                  limit: int = 100) -> Dict[str, Any]:
        """List files in cloud storage"""
        
        if provider not in self.providers:
            return {'success': False, 'error': f'Provider {provider} not available'}
        
        try:
            return self.providers[provider].list_files(prefix, limit)
        except Exception as e:
            logger.error(f"Cloud list failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_file(self, cloud_path: str, provider: str = 's3') -> Dict[str, Any]:
        """Delete file from cloud storage"""
        
        if provider not in self.providers:
            return {'success': False, 'error': f'Provider {provider} not available'}
        
        try:
            return self.providers[provider].delete_file(cloud_path)
        except Exception as e:
            logger.error(f"Cloud delete failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about available providers"""
        
        return {
            'available_providers': list(self.providers.keys()),
            'provider_status': {
                name: provider.get_status() 
                for name, provider in self.providers.items()
            }
        }


class S3StorageProvider:
    """AWS S3 storage provider"""
    
    def __init__(self):
        self.bucket_name = getattr(config, 'AWS_S3_BUCKET', 'qr-bot-storage')
        self.region = getattr(config, 'AWS_REGION', 'us-east-1')
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
                region_name=self.region
            )
            
            # Test connection
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            
        except NoCredentialsError:
            raise Exception("AWS credentials not found")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise Exception(f"S3 bucket {self.bucket_name} not found")
            raise
    
    def upload_file(self, file_path: str, destination_path: str = None,
                   metadata: Dict = None) -> Dict[str, Any]:
        """Upload file to S3"""
        
        try:
            if not destination_path:
                destination_path = os.path.basename(file_path)
            
            # Prepare metadata
            s3_metadata = {}
            if metadata:
                s3_metadata = {
                    'user_id': str(metadata.get('user_id', '')),
                    'qr_id': str(metadata.get('qr_id', '')),
                    'created_at': metadata.get('created_at', datetime.now().isoformat())
                }
            
            # Upload file
            extra_args = {
                'Metadata': s3_metadata,
                'ContentType': self._get_content_type(file_path)
            }
            
            self.s3_client.upload_file(
                file_path, 
                self.bucket_name, 
                destination_path,
                ExtraArgs=extra_args
            )
            
            # Generate URL
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{destination_path}"
            
            return {
                'success': True,
                'url': url,
                'cloud_path': destination_path,
                'provider': 's3',
                'size': os.path.getsize(file_path)
            }
            
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def download_file(self, cloud_path: str, local_path: str = None) -> Dict[str, Any]:
        """Download file from S3"""
        
        try:
            if not local_path:
                local_path = os.path.basename(cloud_path)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            self.s3_client.download_file(self.bucket_name, cloud_path, local_path)
            
            return {
                'success': True,
                'local_path': local_path,
                'cloud_path': cloud_path,
                'size': os.path.getsize(local_path)
            }
            
        except Exception as e:
            logger.error(f"S3 download failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def list_files(self, prefix: str = None, limit: int = 100) -> Dict[str, Any]:
        """List files in S3 bucket"""
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                PaginationConfig={'MaxItems': limit}
            )
            
            files = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'url': f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{obj['Key']}"
                        })
            
            return {
                'success': True,
                'files': files,
                'total': len(files)
            }
            
        except Exception as e:
            logger.error(f"S3 list failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_file(self, cloud_path: str) -> Dict[str, Any]:
        """Delete file from S3"""
        
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=cloud_path)
            
            return {
                'success': True,
                'message': f'File {cloud_path} deleted successfully'
            }
            
        except Exception as e:
            logger.error(f"S3 delete failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_content_type(self, file_path: str) -> str:
        """Get content type for file"""
        
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.json': 'application/json'
        }
        
        return content_types.get(ext, 'application/octet-stream')
    
    def get_status(self) -> Dict[str, Any]:
        """Get S3 provider status"""
        
        try:
            # Test bucket access
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            
            return {
                'status': 'healthy',
                'bucket': self.bucket_name,
                'region': self.region
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }


class GoogleDriveProvider:
    """Google Drive storage provider"""
    
    def __init__(self):
        self.scopes = ['https://www.googleapis.com/auth/drive']
        self.credentials_path = getattr(config, 'GOOGLE_CREDENTIALS_PATH', 'credentials.json')
        self.token_path = getattr(config, 'GOOGLE_TOKEN_PATH', 'token.json')
        
        try:
            self.creds = self._get_credentials()
            self.service = build('drive', 'v3', credentials=self.creds)
            
        except Exception as e:
            raise Exception(f"Failed to initialize Google Drive: {e}")
    
    def _get_credentials(self):
        """Get Google credentials"""
        
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.scopes)
                creds = flow.run_local_server(port=0)
            
            # Save credentials
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        return creds
    
    def upload_file(self, file_path: str, destination_path: str = None,
                   metadata: Dict = None) -> Dict[str, Any]:
        """Upload file to Google Drive"""
        
        try:
            if not destination_path:
                destination_path = os.path.basename(file_path)
            
            # Prepare file metadata
            file_metadata = {
                'name': destination_path,
                'properties': {
                    'provider': 'gdrive',
                    'uploaded_at': datetime.now().isoformat()
                }
            }
            
            if metadata:
                file_metadata['properties'].update({
                    'user_id': str(metadata.get('user_id', '')),
                    'qr_id': str(metadata.get('qr_id', ''))
                })
            
            # Upload file
            media = MediaIoBaseUpload(
                open(file_path, 'rb'),
                mimetype=self._get_content_type(file_path),
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,webViewLink'
            ).execute()
            
            return {
                'success': True,
                'file_id': file['id'],
                'url': file.get('webViewLink', ''),
                'cloud_path': file['name'],
                'provider': 'gdrive',
                'size': int(file['size'])
            }
            
        except Exception as e:
            logger.error(f"Google Drive upload failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def download_file(self, cloud_path: str, local_path: str = None) -> Dict[str, Any]:
        """Download file from Google Drive"""
        
        try:
            if not local_path:
                local_path = os.path.basename(cloud_path)
            
            # Find file by name
            results = self.service.files().list(
                q=f"name='{cloud_path}'",
                fields="files(id,name,size)"
            ).execute()
            
            files = results.get('files', [])
            if not files:
                return {'success': False, 'error': 'File not found'}
            
            file_id = files[0]['id']
            
            # Download file
            request = self.service.files().get_media(fileId=file_id)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            
            return {
                'success': True,
                'local_path': local_path,
                'cloud_path': cloud_path,
                'size': os.path.getsize(local_path)
            }
            
        except Exception as e:
            logger.error(f"Google Drive download failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def list_files(self, prefix: str = None, limit: int = 100) -> Dict[str, Any]:
        """List files in Google Drive"""
        
        try:
            query = ""
            if prefix:
                query = f"name contains '{prefix}'"
            
            results = self.service.files().list(
                q=query,
                fields="files(id,name,size,createdTime,webViewLink)",
                pageSize=limit
            ).execute()
            
            files = []
            for file in results.get('files', []):
                files.append({
                    'id': file['id'],
                    'name': file['name'],
                    'size': int(file['size']) if 'size' in file else 0,
                    'created_at': file['createdTime'],
                    'url': file.get('webViewLink', '')
                })
            
            return {
                'success': True,
                'files': files,
                'total': len(files)
            }
            
        except Exception as e:
            logger.error(f"Google Drive list failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_file(self, cloud_path: str) -> Dict[str, Any]:
        """Delete file from Google Drive"""
        
        try:
            # Find file by name
            results = self.service.files().list(
                q=f"name='{cloud_path}'",
                fields="files(id)"
            ).execute()
            
            files = results.get('files', [])
            if not files:
                return {'success': False, 'error': 'File not found'}
            
            file_id = files[0]['id']
            
            # Delete file
            self.service.files().delete(fileId=file_id).execute()
            
            return {
                'success': True,
                'message': f'File {cloud_path} deleted successfully'
            }
            
        except Exception as e:
            logger.error(f"Google Drive delete failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_content_type(self, file_path: str) -> str:
        """Get content type for file"""
        
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.json': 'application/json'
        }
        
        return content_types.get(ext, 'application/octet-stream')
    
    def get_status(self) -> Dict[str, Any]:
        """Get Google Drive provider status"""
        
        try:
            # Test API access
            results = self.service.files().list(
                pageSize=1,
                fields="files(id)"
            ).execute()
            
            return {
                'status': 'healthy',
                'provider': 'gdrive'
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }


# Global instance
cloud_storage_manager = CloudStorageManager()

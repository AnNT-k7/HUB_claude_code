"""
Tier 2 & 3 Support Service — Storage Service.

Handles uploading, downloading, and generating presigned URLs
for documents stored in MinIO (S3-Compatible Storage).
"""
import io
from minio import Minio
from minio.error import S3Error
from app.config import get_settings

settings = get_settings()

# Initialize MinIO client
# Remove 'http://' or 'https://' from the endpoint since Minio() expects hostname:port
_endpoint = settings.minio_url.replace("http://", "").replace("https://", "")

storage_client = Minio(
    _endpoint,
    access_key=settings.minio_root_user,
    secret_key=settings.minio_root_password,
    secure=settings.minio_secure,
)

def _ensure_bucket_exists(bucket_name: str) -> None:
    """Check if a bucket exists, and create it if it doesn't."""
    try:
        found = storage_client.bucket_exists(bucket_name)
        if not found:
            storage_client.make_bucket(bucket_name)
    except S3Error as err:
        print(f"Error ensuring bucket exists: {err}")
        raise

def upload_document(file_bytes: bytes, filename: str, content_type: str = "application/pdf") -> str:
    """
    Upload a document to MinIO.
    Returns the storage path (e.g., s3://bucket/filename).
    """
    _ensure_bucket_exists(settings.minio_bucket_name)
    file_stream = io.BytesIO(file_bytes)
    file_size = len(file_bytes)
    
    try:
        storage_client.put_object(
            bucket_name=settings.minio_bucket_name,
            object_name=filename,
            data=file_stream,
            length=file_size,
            content_type=content_type
        )
        return f"s3://{settings.minio_bucket_name}/{filename}"
    except S3Error as err:
        print(f"Error uploading document: {err}")
        raise

def get_presigned_url(storage_path: str, expires_in_minutes: int = 15) -> str:
    """
    Generate a temporary presigned URL for a document.
    """
    if not storage_path.startswith("s3://"):
        return ""
        
    parts = storage_path.replace("s3://", "").split("/", 1)
    if len(parts) != 2:
        return ""
        
    bucket_name, object_name = parts
    try:
        # Generate presigned GET URL
        from datetime import timedelta
        url = storage_client.get_presigned_url(
            "GET",
            bucket_name,
            object_name,
            expires=timedelta(minutes=expires_in_minutes),
        )
        return url
    except S3Error as err:
        print(f"Error generating presigned URL: {err}")
        raise

def get_document_bytes(storage_path: str) -> bytes:
    """
    Download a document's raw bytes from MinIO.
    """
    if not storage_path.startswith("s3://"):
        raise ValueError("Invalid storage path")
        
    parts = storage_path.replace("s3://", "").split("/", 1)
    if len(parts) != 2:
        raise ValueError("Invalid storage path")
        
    bucket_name, object_name = parts
    try:
        response = storage_client.get_object(bucket_name, object_name)
        return response.read()
    except S3Error as err:
        print(f"Error downloading document bytes: {err}")
        raise
    finally:
        if 'response' in locals():
            response.close()
            response.release_conn()

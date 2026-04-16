"""
File Storage Service — abstraction layer for local filesystem, Azure Blob, and S3.
Swap backend by setting STORAGE_BACKEND in .env
"""
import os
import uuid
import aiofiles
import logging
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class FileStorageService:

    def __init__(self):
        self.backend = settings.storage_backend.lower()
        self.local_base = Path(settings.local_storage_path)

    async def save_upload(self, file_bytes: bytes, original_filename: str, job_id: str) -> dict:
        """Save an uploaded file and return storage metadata."""
        ext = Path(original_filename).suffix.lower()
        stored_name = f"{job_id}/{uuid.uuid4().hex}{ext}"

        if self.backend == "local":
            return await self._save_local(file_bytes, stored_name, original_filename)
        elif self.backend == "azure":
            return await self._save_azure(file_bytes, stored_name, original_filename)
        elif self.backend in ("s3", "aws"):
            return await self._save_s3(file_bytes, stored_name, original_filename)
        else:
            raise ValueError(f"Unknown storage backend: {self.backend}")

    async def save_output(self, file_bytes: bytes, filename: str, job_id: str) -> dict:
        """Save a generated output file (Excel, PDF)."""
        stored_name = f"outputs/{job_id}/{filename}"
        if self.backend == "local":
            return await self._save_local(file_bytes, stored_name, filename, subfolder="outputs")
        elif self.backend == "azure":
            return await self._save_azure(file_bytes, stored_name, filename)
        elif self.backend in ("s3", "aws"):
            return await self._save_s3(file_bytes, stored_name, filename)
        else:
            raise ValueError(f"Unknown storage backend: {self.backend}")

    async def get_file(self, storage_path: str) -> bytes:
        """Retrieve file bytes from storage."""
        if self.backend == "local":
            full_path = self.local_base / storage_path
            async with aiofiles.open(full_path, "rb") as f:
                return await f.read()
        else:
            raise NotImplementedError(f"get_file not implemented for {self.backend}")

    async def _save_local(self, file_bytes: bytes, stored_name: str, original_filename: str, subfolder: str = "uploads") -> dict:
        target_path = self.local_base / subfolder / stored_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target_path, "wb") as f:
            await f.write(file_bytes)
        relative_path = f"{subfolder}/{stored_name}"
        url = f"/storage/{relative_path}"
        logger.info(f"Saved file to {target_path}")
        return {
            "storage_path": relative_path,
            "storage_url": url,
            "stored_filename": stored_name,
            "file_size": len(file_bytes),
        }

    async def _save_azure(self, file_bytes: bytes, blob_name: str, original_filename: str) -> dict:
        """Azure Blob Storage upload."""
        from azure.storage.blob.aio import BlobServiceClient
        async with BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        ) as client:
            container = client.get_container_client(settings.azure_container_name)
            blob = container.get_blob_client(blob_name)
            await blob.upload_blob(file_bytes, overwrite=True)
            url = blob.url
        return {
            "storage_path": blob_name,
            "storage_url": url,
            "stored_filename": blob_name,
            "file_size": len(file_bytes),
        }

    async def _save_s3(self, file_bytes: bytes, key: str, original_filename: str) -> dict:
        """AWS S3 upload."""
        import aioboto3
        session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        async with session.client("s3") as s3:
            await s3.put_object(Bucket=settings.aws_bucket_name, Key=key, Body=file_bytes)
        url = f"https://{settings.aws_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{key}"
        return {
            "storage_path": key,
            "storage_url": url,
            "stored_filename": key,
            "file_size": len(file_bytes),
        }


# Singleton
storage_service = FileStorageService()

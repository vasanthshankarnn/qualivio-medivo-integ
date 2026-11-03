"""Azure Blob access, same approach as caller-qa-py/app/blob/blob_storage.py."""
import mimetypes
import re
from datetime import datetime, timedelta, timezone

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, ContentSettings, generate_blob_sas

from app.config import AZURE_RECORDING_CONTAINER_NAME, AZURE_STORAGE_CONNECTION_STRING


class BlobStorage:
    def __init__(self):
        if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_RECORDING_CONTAINER_NAME:
            raise ValueError("Azure Blob settings are missing")
        self.container = AZURE_RECORDING_CONTAINER_NAME
        self.service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        self.client = self.service.get_container_client(self.container)

    def upload_file(self, blob_key: str, local_path: str) -> str:
        blob_key = blob_key.replace("\\", "/").lstrip("/")
        ct = mimetypes.guess_type(blob_key)[0] or "application/octet-stream"
        with open(local_path, "rb") as f:
            self.client.get_blob_client(blob_key).upload_blob(f, overwrite=True, content_settings=ContentSettings(content_type=ct))
        return blob_key

    def sas_url(self, blob_key: str, expiry_hours: int = 2) -> str:
        match = re.search(r"AccountKey=([^;]+)", AZURE_STORAGE_CONNECTION_STRING)
        if not match:
            raise ValueError("AccountKey not found in AZURE_STORAGE_CONNECTION_STRING (needed for SAS)")
        token = generate_blob_sas(
            account_name=self.service.account_name,
            container_name=self.container,
            blob_name=blob_key,
            account_key=match.group(1),
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
        )
        return f"{self.client.get_blob_client(blob_key).url}?{token}"

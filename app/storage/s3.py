import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException
from typing import Optional

from .base import StorageBackend


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""

    def __init__(
        self,
        bucket_name: str,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        self.bucket_name = bucket_name

        # Initialize S3 client
        self.s3 = boto3.client(
            "s3",
            region_name=region_name,
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    async def save(
        self, filename: str, file: UploadFile, is_public: bool = False
    ) -> str:
        """Save a file to S3."""
        try:
            # Set ACL based on public/private status
            extra_args = {"ACL": "public-read"} if is_public else {}

            # Upload the file
            self.s3.upload_fileobj(
                file.file,
                self.bucket_name,
                filename,
                ExtraArgs=extra_args,
            )

            return filename
        except ClientError as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to upload file to S3: {str(e)}"
            )

    async def get_url(
        self, filename: str, is_public: bool = False, expires_in: int = 3600
    ) -> str:
        """Get a URL for accessing the file."""
        try:
            if is_public:
                # For public files, return the direct S3 URL
                return f"https://{self.bucket_name}.s3.amazonaws.com/{filename}"
            else:
                # For private files, generate a presigned URL
                return self.s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": filename},
                    ExpiresIn=expires_in,
                )
        except ClientError as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to generate URL: {str(e)}"
            )

    async def delete(self, filename: str) -> bool:
        """Delete a file from S3."""
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=filename)
            return True
        except ClientError:
            return False

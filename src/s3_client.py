"""S3 client for listing and downloading vCon JSON files."""

import logging
import json
from typing import List, Optional, Iterator
from datetime import datetime
from botocore.exceptions import ClientError, BotoCoreError
import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


class S3Client:
    """Client for interacting with S3 to list and download vCon files."""

    def __init__(self, bucket_name: str, prefix: str = "", region: str = "us-east-1"):
        """
        Initialize S3 client.

        Args:
            bucket_name: Name of the S3 bucket
            prefix: Optional prefix to filter objects
            region: AWS region
        """
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip("/")
        self.region = region
        
        # Configure retries
        config = Config(
            retries={
                "max_attempts": 3,
                "mode": "adaptive",
            }
        )
        
        self.s3_client = boto3.client("s3", region_name=region, config=config)

    def list_objects_by_date(self, date: datetime) -> List[str]:
        """
        List all JSON objects for a specific date.

        Args:
            date: Date to list objects for (YYYY/MM/DD format)

        Returns:
            List of S3 object keys
        """
        date_prefix = date.strftime("%Y/%m/%d")
        prefix = f"{self.prefix}/{date_prefix}" if self.prefix else date_prefix
        prefix = prefix.lstrip("/")
        
        logger.debug(f"Listing S3 objects: bucket={self.bucket_name}, prefix={prefix}, date={date_prefix}")
        
        try:
            objects = []
            paginator = self.s3_client.get_paginator("list_objects_v2")
            page_count = 0
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                page_count += 1
                if "Contents" in page:
                    page_objects = len(page["Contents"])
                    logger.debug(f"Processing S3 page {page_count}: found {page_objects} objects")
                    for obj in page["Contents"]:
                        key = obj["Key"]
                        size = obj.get("Size", 0)
                        # Filter for JSON files, vCon files (.json, .vcon.json, .vcon)
                        key_lower = key.lower()
                        if key_lower.endswith(".json") or key_lower.endswith(".vcon.json") or key_lower.endswith(".vcon"):
                            objects.append(key)
                            logger.debug(f"Found vCon/JSON object: {key}, size={size} bytes")
                        else:
                            logger.debug(f"Skipping non-vCon/JSON object: {key}")
                else:
                    logger.debug(f"S3 page {page_count} has no contents")
            
            logger.info(f"Found {len(objects)} vCon/JSON objects for date {date_prefix} in {page_count} page(s)")
            if objects:
                logger.debug(f"Object keys: {objects[:5]}{'...' if len(objects) > 5 else ''}")
            return objects
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = e.response.get("Error", {}).get("Message", "")
            if error_code == "NoSuchBucket":
                logger.error(f"Bucket {self.bucket_name} does not exist (prefix={prefix})")
                raise
            logger.error(f"Error listing objects for date {date_prefix}: error_code={error_code}, error_message={error_message}, prefix={prefix}")
            raise
        except BotoCoreError as e:
            logger.error(f"AWS error listing objects for date {date_prefix}: error_type={type(e).__name__}, error={str(e)}, prefix={prefix}")
            raise

    def list_all_dates(self, start_date: datetime, end_date: datetime) -> Iterator[tuple[datetime, List[str]]]:
        """
        List all dates and their objects between start_date and end_date.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Yields:
            Tuples of (date, list of object keys)
        """
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            date_obj = datetime.combine(current_date, datetime.min.time())
            try:
                objects = self.list_objects_by_date(date_obj)
                yield (date_obj, objects)
            except Exception as e:
                logger.error(f"Error processing date {current_date}: {e}")
                # Continue with next date
            current_date = self._next_date(current_date)

    def _next_date(self, date) -> datetime.date:
        """Get next date."""
        from datetime import timedelta
        return date + timedelta(days=1)

    def download_object(self, key: str) -> Optional[bytes]:
        """
        Download an object from S3.

        Args:
            key: S3 object key

        Returns:
            Object content as bytes, or None if error
        """
        logger.debug(f"Downloading object from S3: bucket={self.bucket_name}, key={key}")
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            content_length = response.get("ContentLength", 0)
            content_type = response.get("ContentType", "unknown")
            logger.debug(f"S3 response metadata: ContentLength={content_length}, ContentType={content_type}")
            
            content = response["Body"].read()
            actual_size = len(content)
            logger.debug(f"Downloaded object {key}: expected_size={content_length}, actual_size={actual_size} bytes, content_type={content_type}")
            
            if content_length > 0 and actual_size != content_length:
                logger.warning(f"Size mismatch for {key}: expected={content_length}, actual={actual_size}")
            
            return content
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = e.response.get("Error", {}).get("Message", "")
            if error_code == "NoSuchKey":
                logger.warning(f"Object {key} does not exist in bucket {self.bucket_name}")
                return None
            logger.error(f"Error downloading object {key}: error_code={error_code}, error_message={error_message}, bucket={self.bucket_name}")
            return None
        except BotoCoreError as e:
            logger.error(f"AWS error downloading object {key}: error_type={type(e).__name__}, error={str(e)}, bucket={self.bucket_name}")
            return None

    def download_json(self, key: str) -> Optional[dict]:
        """
        Download and parse a JSON object from S3.

        Args:
            key: S3 object key

        Returns:
            Parsed JSON as dict, or None if error
        """
        content = self.download_object(key)
        if content is None:
            return None
        
        try:
            # Try to decode as UTF-8
            text = content.decode("utf-8")
            return json.loads(text)
        except UnicodeDecodeError as e:
            logger.error(f"Error decoding object {key} as UTF-8: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from object {key}: {e}")
            return None

    def object_exists(self, key: str) -> bool:
        """
        Check if an object exists in S3.

        Args:
            key: S3 object key

        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                return False
            logger.error(f"Error checking object {key}: {e}")
            return False
        except BotoCoreError as e:
            logger.error(f"AWS error checking object {key}: {e}")
            return False


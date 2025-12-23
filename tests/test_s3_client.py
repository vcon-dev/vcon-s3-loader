"""Tests for S3 client."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from botocore.exceptions import ClientError
from src.s3_client import S3Client


@pytest.fixture
def s3_client():
    """Create S3 client instance."""
    with patch("src.s3_client.boto3"):
        client = S3Client(bucket_name="test-bucket", prefix="vcons/", region="us-east-1")
        client.s3_client = Mock()
        return client


def test_list_objects_by_date(s3_client):
    """Test listing objects by date."""
    date_obj = datetime(2024, 1, 15)
    
    # Mock paginator and pages
    page_data = {
        "Contents": [
            {"Key": "vcons/2024/01/15/vcon1.json"},
            {"Key": "vcons/2024/01/15/vcon2.json"},
            {"Key": "vcons/2024/01/15/other.txt"},  # Should be filtered out
        ]
    }
    
    paginator_mock = Mock()
    paginator_mock.paginate.return_value = [page_data]
    s3_client.s3_client.get_paginator.return_value = paginator_mock
    
    objects = s3_client.list_objects_by_date(date_obj)
    assert len(objects) == 2
    assert "vcons/2024/01/15/vcon1.json" in objects
    assert "vcons/2024/01/15/vcon2.json" in objects


def test_download_object(s3_client):
    """Test downloading an object."""
    s3_client.s3_client.get_object.return_value = {
        "Body": Mock(read=Mock(return_value=b'{"test": "data"}'))
    }
    
    content = s3_client.download_object("test-key.json")
    assert content == b'{"test": "data"}'


def test_download_object_not_found(s3_client):
    """Test downloading non-existent object."""
    error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
    s3_client.s3_client.get_object.side_effect = error
    
    content = s3_client.download_object("nonexistent.json")
    assert content is None


def test_download_json(s3_client):
    """Test downloading and parsing JSON."""
    s3_client.s3_client.get_object.return_value = {
        "Body": Mock(read=Mock(return_value=b'{"test": "data"}'))
    }
    
    data = s3_client.download_json("test-key.json")
    assert data == {"test": "data"}


def test_download_json_invalid(s3_client):
    """Test downloading invalid JSON."""
    s3_client.s3_client.get_object.return_value = {
        "Body": Mock(read=Mock(return_value=b'invalid json'))
    }
    
    data = s3_client.download_json("test-key.json")
    assert data is None


def test_object_exists(s3_client):
    """Test checking if object exists."""
    s3_client.s3_client.head_object.return_value = {}
    
    assert s3_client.object_exists("test-key.json") is True


def test_object_not_exists(s3_client):
    """Test checking if object doesn't exist."""
    error = ClientError({"Error": {"Code": "404"}}, "HeadObject")
    s3_client.s3_client.head_object.side_effect = error
    
    assert s3_client.object_exists("nonexistent.json") is False


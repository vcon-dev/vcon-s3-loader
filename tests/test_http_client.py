"""Tests for HTTP client."""

import pytest
from unittest.mock import Mock, patch
import requests
from requests.exceptions import Timeout, ConnectionError as RequestsConnectionError
from src.http_client import HTTPClient


@pytest.fixture
def http_client():
    """Create HTTP client instance."""
    return HTTPClient(
        url="https://api.example.com/vcons",
        headers={"Authorization": "Bearer token"},
        retry_attempts=3,
        retry_backoff_base=1,
    )


@patch("src.http_client.requests.post")
def test_post_vcon_success(mock_post, http_client):
    """Test successful POST."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    
    vcon_data = {"vcon": "0.0.1", "uuid": "test-uuid"}
    result = http_client.post_vcon(vcon_data)
    
    assert result is True
    mock_post.assert_called_once()


@patch("src.http_client.requests.post")
def test_post_vcon_retry_on_timeout(mock_post, http_client):
    """Test retry on timeout."""
    mock_post.side_effect = [Timeout("Timeout"), Mock(status_code=200)]
    
    vcon_data = {"vcon": "0.0.1", "uuid": "test-uuid"}
    result = http_client.post_vcon(vcon_data)
    
    assert result is True
    assert mock_post.call_count == 2


@patch("src.http_client.requests.post")
def test_post_vcon_client_error_no_retry(mock_post, http_client):
    """Test no retry on 4xx client errors."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    error = requests.exceptions.RequestException()
    error.response = mock_response
    mock_post.side_effect = error
    
    vcon_data = {"vcon": "0.0.1", "uuid": "test-uuid"}
    result = http_client.post_vcon(vcon_data)
    
    assert result is False
    assert mock_post.call_count == 1


def test_determine_content_type_json(http_client):
    """Test Content-Type determination for JSON."""
    vcon_data = {"vcon": "0.0.1", "uuid": "test-uuid"}
    content_type = http_client._determine_content_type(vcon_data)
    assert content_type == "application/json"


def test_determine_content_type_jws(http_client):
    """Test Content-Type determination for JWS."""
    vcon_data = {
        "payload": "base64encoded",
        "signatures": [{"signature": "sig"}]
    }
    content_type = http_client._determine_content_type(vcon_data)
    assert content_type == "application/jose+json"


def test_determine_content_type_jwe(http_client):
    """Test Content-Type determination for JWE."""
    vcon_data = {
        "ciphertext": "encrypted",
        "encrypted_key": "key"
    }
    content_type = http_client._determine_content_type(vcon_data)
    assert content_type == "application/jose+json"


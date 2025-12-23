"""Tests for vCon loader."""

import pytest
from unittest.mock import Mock, patch
from src.vcon_loader import VConLoader


@pytest.fixture
def sample_vcon_data():
    """Sample vCon data."""
    return {
        "vcon": "0.0.1",
        "uuid": "test-uuid-12345",
        "created_at": "2024-01-01T10:00:00Z",
        "parties": [{"name": "Alice"}],
        "dialog": [{"type": "text", "body": "Hello"}]
    }


@patch("src.vcon_loader.Vcon")
def test_load_from_dict(mock_vcon_class, sample_vcon_data):
    """Test loading vCon from dictionary."""
    mock_vcon = Mock()
    mock_vcon.is_valid.return_value = (True, [])
    mock_vcon.uuid = "test-uuid-12345"
    mock_vcon_class.build_from_json.return_value = mock_vcon
    
    loader = VConLoader(validate=True)
    vcon = loader.load_from_dict(sample_vcon_data)
    
    assert vcon is not None
    mock_vcon.is_valid.assert_called_once()


@patch("src.vcon_loader.Vcon")
def test_load_from_dict_validation_failure(mock_vcon_class, sample_vcon_data):
    """Test loading vCon with validation failure."""
    mock_vcon = Mock()
    mock_vcon.is_valid.return_value = (False, ["Validation error"])
    mock_vcon_class.build_from_json.return_value = mock_vcon
    
    loader = VConLoader(validate=True)
    vcon = loader.load_from_dict(sample_vcon_data)
    
    assert vcon is None


@patch("src.vcon_loader.Vcon")
def test_load_from_dict_no_validation(mock_vcon_class, sample_vcon_data):
    """Test loading vCon without validation."""
    mock_vcon = Mock()
    mock_vcon.uuid = "test-uuid-12345"
    mock_vcon_class.build_from_json.return_value = mock_vcon
    
    loader = VConLoader(validate=False)
    vcon = loader.load_from_dict(sample_vcon_data)
    
    assert vcon is not None
    mock_vcon.is_valid.assert_not_called()


def test_extract_uuid(sample_vcon_data):
    """Test extracting UUID from vCon."""
    with patch("src.vcon_loader.Vcon") as mock_vcon_class:
        mock_vcon = Mock()
        mock_vcon.uuid = "test-uuid-12345"
        mock_vcon.is_valid.return_value = (True, [])
        mock_vcon_class.build_from_json.return_value = mock_vcon
        
        loader = VConLoader(validate=False)
        vcon = loader.load_from_dict(sample_vcon_data)
        uuid = loader.extract_uuid(vcon)
        
        assert uuid == "test-uuid-12345"


def test_extract_identifier_with_s3_key(sample_vcon_data):
    """Test extracting identifier with S3 key fallback."""
    with patch("src.vcon_loader.Vcon") as mock_vcon_class:
        mock_vcon = Mock()
        mock_vcon.uuid = None
        mock_vcon.to_json.return_value = '{"test": "data"}'
        mock_vcon.is_valid.return_value = (True, [])
        mock_vcon_class.build_from_json.return_value = mock_vcon
        
        loader = VConLoader(validate=False)
        vcon = loader.load_from_dict(sample_vcon_data)
        identifier = loader.extract_identifier(vcon, s3_key="test-key.json")
        
        assert identifier == "test-key.json"


def test_is_jws_format():
    """Test JWS format detection."""
    loader = VConLoader()
    jws_data = {
        "payload": "base64encoded",
        "signatures": [{"signature": "sig"}]
    }
    assert loader._is_jws_format(jws_data) is True
    
    normal_data = {"vcon": "0.0.1"}
    assert loader._is_jws_format(normal_data) is False


def test_is_jwe_format():
    """Test JWE format detection."""
    loader = VConLoader()
    jwe_data = {
        "ciphertext": "encrypted",
        "encrypted_key": "key"
    }
    assert loader._is_jwe_format(jwe_data) is True
    
    normal_data = {"vcon": "0.0.1"}
    assert loader._is_jwe_format(normal_data) is False


@patch("src.vcon_loader.Vcon")
def test_load_from_dict_jws_format(mock_vcon_class):
    """Test loading JWS format vCon."""
    jws_data = {
        "uuid": "jws-uuid",
        "payload": "base64encoded",
        "signatures": [{"signature": "sig"}]
    }
    
    mock_vcon = Mock()
    mock_vcon.is_valid.return_value = (True, [])
    mock_vcon.uuid = "jws-uuid"
    mock_vcon_class.build_from_json.return_value = mock_vcon
    
    loader = VConLoader(validate=True)
    vcon = loader.load_from_dict(jws_data)
    
    assert vcon is not None
    mock_vcon_class.build_from_json.assert_called_once()


@patch("src.vcon_loader.Vcon")
def test_load_from_dict_jwe_format(mock_vcon_class):
    """Test loading JWE format vCon."""
    jwe_data = {
        "uuid": "jwe-uuid",
        "ciphertext": "encrypted",
        "encrypted_key": "key"
    }
    
    mock_vcon = Mock()
    mock_vcon.is_valid.return_value = (True, [])
    mock_vcon.uuid = "jwe-uuid"
    mock_vcon_class.build_from_json.return_value = mock_vcon
    
    loader = VConLoader(validate=True)
    vcon = loader.load_from_dict(jwe_data)
    
    assert vcon is not None


@patch("src.vcon_loader.Vcon")
def test_load_from_dict_error_handling(mock_vcon_class, sample_vcon_data):
    """Test error handling in load_from_dict."""
    # Test ValueError/TypeError handling
    mock_vcon_class.build_from_json.side_effect = ValueError("Invalid vCon format")
    
    loader = VConLoader(validate=True)
    vcon = loader.load_from_dict(sample_vcon_data)
    
    assert vcon is None


@patch("src.vcon_loader.Vcon")
def test_load_from_dict_general_exception(mock_vcon_class, sample_vcon_data):
    """Test general exception handling in load_from_dict."""
    mock_vcon_class.build_from_json.side_effect = Exception("Unexpected error")
    
    loader = VConLoader(validate=True)
    vcon = loader.load_from_dict(sample_vcon_data)
    
    assert vcon is None


def test_load_from_json_string():
    """Test loading vCon from JSON string."""
    with patch("src.vcon_loader.Vcon") as mock_vcon_class:
        mock_vcon = Mock()
        mock_vcon.is_valid.return_value = (True, [])
        mock_vcon.uuid = "test-uuid"
        mock_vcon_class.build_from_json.return_value = mock_vcon
        
        loader = VConLoader(validate=True)
        json_str = '{"vcon": "0.0.1", "uuid": "test-uuid", "parties": []}'
        vcon = loader.load_from_json_string(json_str)
        
        assert vcon is not None


def test_load_from_json_string_invalid_json():
    """Test loading vCon from invalid JSON string."""
    loader = VConLoader(validate=True)
    invalid_json = "not valid json"
    vcon = loader.load_from_json_string(invalid_json)
    
    assert vcon is None


def test_load_from_json_string_error():
    """Test error handling in load_from_json_string."""
    loader = VConLoader(validate=True)
    # This will cause an error in load_from_dict
    with patch.object(loader, 'load_from_dict', side_effect=Exception("Test error")):
        json_str = '{"vcon": "0.0.1"}'
        vcon = loader.load_from_json_string(json_str)
        assert vcon is None


def test_load_from_bytes():
    """Test loading vCon from bytes."""
    with patch("src.vcon_loader.Vcon") as mock_vcon_class:
        mock_vcon = Mock()
        mock_vcon.is_valid.return_value = (True, [])
        mock_vcon.uuid = "test-uuid"
        mock_vcon_class.build_from_json.return_value = mock_vcon
        
        loader = VConLoader(validate=True)
        content = b'{"vcon": "0.0.1", "uuid": "test-uuid", "parties": []}'
        vcon = loader.load_from_bytes(content)
        
        assert vcon is not None


def test_load_from_bytes_unicode_error():
    """Test loading vCon from bytes with Unicode decode error."""
    loader = VConLoader(validate=True)
    # Invalid UTF-8 bytes
    invalid_bytes = b'\xff\xfe\x00\x01'
    vcon = loader.load_from_bytes(invalid_bytes)
    
    assert vcon is None


def test_load_from_bytes_error():
    """Test error handling in load_from_bytes."""
    loader = VConLoader(validate=True)
    with patch.object(loader, 'load_from_json_string', side_effect=Exception("Test error")):
        content = b'{"vcon": "0.0.1"}'
        vcon = loader.load_from_bytes(content)
        assert vcon is None


def test_extract_uuid_error():
    """Test extract_uuid with error."""
    from unittest.mock import PropertyMock
    loader = VConLoader()
    mock_vcon = Mock()
    type(mock_vcon).uuid = PropertyMock(side_effect=Exception("UUID error"))
    
    uuid = loader.extract_uuid(mock_vcon)
    assert uuid is None


def test_extract_identifier_hash_fallback():
    """Test extract_identifier with hash fallback."""
    loader = VConLoader()
    mock_vcon = Mock()
    mock_vcon.uuid = None
    mock_vcon.to_json.return_value = '{"test": "data"}'
    
    identifier = loader.extract_identifier(mock_vcon, s3_key=None)
    
    # Should return MD5 hash
    assert identifier is not None
    assert len(identifier) == 32  # MD5 hex digest length


def test_extract_identifier_with_uuid():
    """Test extract_identifier with UUID."""
    loader = VConLoader()
    mock_vcon = Mock()
    mock_vcon.uuid = "test-uuid-123"
    
    identifier = loader.extract_identifier(mock_vcon, s3_key="fallback-key.json")
    
    assert identifier == "test-uuid-123"


def test_preserve_security_form():
    """Test preserve_security_form method."""
    loader = VConLoader()
    vcon_data = {"vcon": "0.0.1", "uuid": "test-uuid"}
    
    result = loader.preserve_security_form(vcon_data)
    
    assert result == vcon_data
    assert result is vcon_data  # Should return same object


@patch("src.vcon_loader.Vcon")
def test_load_from_dict_with_parties_dialog_attributes(mock_vcon_class, sample_vcon_data):
    """Test loading vCon with parties and dialog attributes."""
    mock_vcon = Mock()
    mock_vcon.is_valid.return_value = (True, [])
    mock_vcon.uuid = "test-uuid-12345"
    # Mock parties and dialog to raise TypeError on len() to test error handling
    mock_vcon.parties = Mock(side_effect=TypeError("Cannot get length"))
    mock_vcon.dialog = Mock(side_effect=AttributeError("No dialog"))
    mock_vcon_class.build_from_json.return_value = mock_vcon
    
    loader = VConLoader(validate=True)
    vcon = loader.load_from_dict(sample_vcon_data)
    
    assert vcon is not None


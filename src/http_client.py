"""HTTP client for POSTing vCons to a configurable URL."""

import logging
import time
import json
from typing import Dict, Any, Optional
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

logger = logging.getLogger(__name__)


class HTTPClient:
    """Client for POSTing vCons to HTTP endpoints."""

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        use_vcon_method: bool = False,
        retry_attempts: int = 3,
        retry_backoff_base: int = 2,
        timeout: int = 30,
    ):
        """
        Initialize HTTP client.

        Args:
            url: Target URL for POST requests
            headers: Custom headers to include in requests
            use_vcon_method: Whether to use vCon library's post_to_url method
            retry_attempts: Number of retry attempts for failed requests
            retry_backoff_base: Base seconds for exponential backoff
            timeout: Request timeout in seconds
        """
        self.url = url
        self.headers = headers or {}
        self.use_vcon_method = use_vcon_method
        self.retry_attempts = retry_attempts
        self.retry_backoff_base = retry_backoff_base
        self.timeout = timeout
        
        # Ensure Content-Type is set
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "application/json"

    def post_vcon(self, vcon_data: Dict[str, Any], vcon_obj: Optional[Any] = None) -> bool:
        """
        POST a vCon to the configured URL.

        Args:
            vcon_data: vCon data as dictionary
            vcon_obj: Optional vCon object (required if use_vcon_method is True)

        Returns:
            True if successful, False otherwise
        """
        if self.use_vcon_method and vcon_obj is not None:
            return self._post_with_vcon_method(vcon_obj)
        else:
            return self._post_with_requests(vcon_data)

    def _post_with_vcon_method(self, vcon_obj: Any) -> bool:
        """
        POST using vCon library's post_to_url method.

        Args:
            vcon_obj: vCon object with post_to_url method

        Returns:
            True if successful, False otherwise
        """
        try:
            response = vcon_obj.post_to_url(self.url, headers=self.headers)
            if response and hasattr(response, "status_code"):
                status_code = response.status_code
                if 200 <= status_code < 300:
                    logger.debug(f"Successfully posted vCon using vCon method (status: {status_code})")
                    return True
                else:
                    logger.warning(f"POST failed with status {status_code}")
                    return False
            # If response doesn't have status_code, assume success
            logger.debug("Successfully posted vCon using vCon method")
            return True
        except Exception as e:
            logger.error(f"Error posting vCon with vCon method: {e}")
            return False

    def _post_with_requests(self, vcon_data: Dict[str, Any]) -> bool:
        """
        POST using requests library with retry logic.

        Args:
            vcon_data: vCon data as dictionary

        Returns:
            True if successful, False otherwise
        """
        last_exception = None
        vcon_uuid = vcon_data.get("uuid", "unknown")
        data_size = len(str(vcon_data))
        
        logger.debug(f"POSTing vCon with requests library: url={self.url}, uuid={vcon_uuid}, data_size={data_size} bytes, timeout={self.timeout}s")
        
        for attempt in range(self.retry_attempts):
            attempt_start = time.time()
            try:
                # Determine Content-Type based on vCon format
                content_type = self._determine_content_type(vcon_data)
                headers = self.headers.copy()
                headers["Content-Type"] = content_type
                logger.debug(f"Attempt {attempt + 1}/{self.retry_attempts}: Content-Type={content_type}, headers={list(headers.keys())}")
                
                # Serialize data
                if content_type == "application/json":
                    data = json.dumps(vcon_data)
                else:
                    # For JWS/JWE, assume it's already a string
                    data = json.dumps(vcon_data) if isinstance(vcon_data, dict) else str(vcon_data)
                
                serialized_size = len(data)
                logger.debug(f"Serialized data size: {serialized_size} bytes")
                
                response = requests.post(
                    self.url,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                )
                
                attempt_time = time.time() - attempt_start
                try:
                    response_size = len(response.content) if response.content else 0
                except (TypeError, AttributeError):
                    # Handle mock objects or responses without content attribute
                    response_size = 0
                logger.debug(f"POST response received: status={response.status_code}, response_size={response_size} bytes, attempt_time={attempt_time:.3f}s")
                
                if 200 <= response.status_code < 300:
                    logger.info(f"Successfully posted vCon: uuid={vcon_uuid}, status={response.status_code}, attempt={attempt + 1}, time={attempt_time:.3f}s")
                    return True
                else:
                    response_preview = response.text[:200] if response.text else "no response body"
                    logger.warning(
                        f"POST failed: uuid={vcon_uuid}, status={response.status_code}, "
                        f"response_preview={response_preview}, attempt={attempt + 1}/{self.retry_attempts}"
                    )
                    last_exception = RequestException(
                        f"HTTP {response.status_code}: {response_preview}"
                    )
                    
            except (Timeout, ConnectionError) as e:
                attempt_time = time.time() - attempt_start
                last_exception = e
                logger.warning(
                    f"Request attempt {attempt + 1}/{self.retry_attempts} failed: "
                    f"uuid={vcon_uuid}, error_type={type(e).__name__}, error={str(e)}, "
                    f"attempt_time={attempt_time:.3f}s"
                )
                
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_backoff_base ** attempt
                    logger.info(f"Retrying POST for uuid={vcon_uuid} in {wait_time} seconds (attempt {attempt + 2}/{self.retry_attempts})")
                    time.sleep(wait_time)
                    
            except RequestException as e:
                attempt_time = time.time() - attempt_start
                last_exception = e
                logger.error(f"Request error: uuid={vcon_uuid}, error_type={type(e).__name__}, error={str(e)}, attempt_time={attempt_time:.3f}s")
                # Don't retry on 4xx errors (client errors)
                if hasattr(e, "response") and e.response is not None:
                    status_code = e.response.status_code
                    if 400 <= status_code < 500:
                        logger.error(f"Client error {status_code} for uuid={vcon_uuid}, not retrying")
                        return False
                # Retry on other errors
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_backoff_base ** attempt
                    logger.info(f"Retrying POST for uuid={vcon_uuid} in {wait_time} seconds (attempt {attempt + 2}/{self.retry_attempts})")
                    time.sleep(wait_time)
                    
            except Exception as e:
                attempt_time = time.time() - attempt_start
                logger.error(f"Unexpected error posting vCon: uuid={vcon_uuid}, error_type={type(e).__name__}, error={str(e)}, attempt_time={attempt_time:.3f}s", exc_info=True)
                return False
        
        if last_exception:
            logger.error(f"Failed to post vCon after {self.retry_attempts} attempts: uuid={vcon_uuid}, final_error={last_exception}")
        return False

    def _determine_content_type(self, vcon_data: Dict[str, Any]) -> str:
        """
        Determine Content-Type based on vCon format.

        Args:
            vcon_data: vCon data

        Returns:
            Content-Type string
        """
        # Check if it's a JWS (signed) or JWE (encrypted) format
        if isinstance(vcon_data, dict):
            # JWS format has "payload" and "signatures" keys
            if "payload" in vcon_data and "signatures" in vcon_data:
                return "application/jose+json"
            # JWE format has "ciphertext" and "encrypted_key" keys
            if "ciphertext" in vcon_data and "encrypted_key" in vcon_data:
                return "application/jose+json"
        
        # Default to JSON
        return "application/json"

    def test_connection(self) -> bool:
        """
        Test connection to the endpoint.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try a HEAD request first
            response = requests.head(self.url, timeout=self.timeout)
            return response.status_code < 500
        except Exception:
            # If HEAD fails, try a simple GET
            try:
                response = requests.get(self.url, timeout=self.timeout)
                return response.status_code < 500
            except Exception as e:
                logger.warning(f"Connection test failed: {e}")
                return False


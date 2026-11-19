"""VCon loader for parsing and validating vCon JSON files.

Built on vcon-lib 1.x (vCon core-05, syntax "0.5.0"). The library reads both
0.4.0 and 0.5.0: an unsigned vCon that declares "0.4.0" is migrated to 0.5.0
when it is loaded, so validation checks the migrated form. Other syntax
versions (pre-0.4.0) are not migrated and fail validation. The document that
is POSTed is the original from S3 unless version migration is enabled.
"""

import logging
import json
from typing import Optional, Dict, Any
from vcon import Vcon

logger = logging.getLogger(__name__)


class VConLoader:
    """Loader for vCon JSON files with optional validation and version migration."""

    def __init__(self, validate: bool = True, migrate_version: bool = False):
        """
        Initialize vCon loader.

        Args:
            validate: Whether to validate vCons using is_valid() (core-05 rules,
                after migrating 0.4.0 input)
            migrate_version: Whether to POST the migrated 0.5.0 form of a
                0.4.0 vCon instead of the original document
        """
        self.validate = validate
        self.migrate_version = migrate_version

    def load_from_dict(self, data: Dict[str, Any]) -> Optional[Vcon]:
        """
        Load vCon from dictionary.

        Args:
            data: vCon data as dictionary

        Returns:
            Vcon object, or None if error
        """
        vcon_uuid = data.get("uuid", "unknown")
        logger.debug(f"Loading vCon from dictionary: uuid={vcon_uuid}, data_keys={list(data.keys())}")
        
        try:
            # Check if it's a signed/encrypted vCon (JWS/JWE format)
            is_jws = self._is_jws_format(data)
            is_jwe = self._is_jwe_format(data)
            
            # Check current vCon version if migration is enabled
            current_version = data.get("vcon", None)
            if self.migrate_version and current_version:
                logger.debug(f"Version migration enabled: current_version={current_version}, uuid={vcon_uuid}")
            
            if is_jws or is_jwe:
                # For signed/encrypted vCons, we preserve the format
                logger.debug(f"Detected signed/encrypted vCon format: uuid={vcon_uuid}, format={'JWS' if is_jws else 'JWE'}")
                # For now, we'll try to build from JSON string
                json_str = json.dumps(data)
                logger.debug(f"Building vCon from JWS/JWE JSON string: uuid={vcon_uuid}, json_size={len(json_str)} bytes")
                vcon = Vcon.build_from_json(json_str)
                
                # Apply version migration if enabled
                if self.migrate_version:
                    vcon = self._migrate_vcon(vcon, vcon_uuid)
            else:
                # Standard vCon format
                logger.debug(f"Detected standard vCon format: uuid={vcon_uuid}")
                json_str = json.dumps(data)
                logger.debug(f"Building vCon from standard JSON: uuid={vcon_uuid}, json_size={len(json_str)} bytes")
                vcon = Vcon.build_from_json(json_str)
                
                # Apply version migration if enabled
                if self.migrate_version:
                    vcon = self._migrate_vcon(vcon, vcon_uuid)
            
            # Safely check vCon properties for logging
            try:
                has_parties = hasattr(vcon, 'parties') and vcon.parties and len(vcon.parties) > 0
            except (TypeError, AttributeError):
                has_parties = hasattr(vcon, 'parties')
            
            try:
                has_dialog = hasattr(vcon, 'dialog') and vcon.dialog and len(vcon.dialog) > 0
            except (TypeError, AttributeError):
                has_dialog = hasattr(vcon, 'dialog')
            
            logger.debug(f"vCon object created: uuid={vcon_uuid}, has_parties={has_parties}, has_dialog={has_dialog}")
            
            # Validate if enabled
            if self.validate:
                logger.debug(f"Validating vCon: uuid={vcon_uuid}")
                is_valid, errors = vcon.is_valid()
                if not is_valid:
                    logger.warning(f"vCon validation failed: uuid={vcon_uuid}, errors={errors}")
                    return None
                logger.debug(f"vCon validation passed: uuid={vcon_uuid}")
            else:
                logger.debug(f"Skipping validation for vCon: uuid={vcon_uuid}")
            
            return vcon
            
        except (ValueError, TypeError) as e:
            # Handle JSON encoding/decoding errors
            logger.error(f"JSON encoding/decoding error loading vCon: uuid={vcon_uuid}, error_type={type(e).__name__}, error={str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error loading vCon from dict: uuid={vcon_uuid}, error_type={type(e).__name__}, error={str(e)}", exc_info=True)
            return None

    def load_from_json_string(self, json_str: str) -> Optional[Vcon]:
        """
        Load vCon from JSON string.

        Args:
            json_str: vCon JSON string

        Returns:
            Vcon object, or None if error
        """
        try:
            data = json.loads(json_str)
            return self.load_from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON string: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading vCon from JSON string: {e}")
            return None

    def load_from_bytes(self, content: bytes) -> Optional[Vcon]:
        """
        Load vCon from bytes.

        Args:
            content: vCon content as bytes

        Returns:
            Vcon object, or None if error
        """
        try:
            text = content.decode("utf-8")
            return self.load_from_json_string(text)
        except UnicodeDecodeError as e:
            logger.error(f"Error decoding bytes as UTF-8: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading vCon from bytes: {e}")
            return None

    def extract_uuid(self, vcon: Vcon) -> Optional[str]:
        """
        Extract UUID from vCon.

        Args:
            vcon: Vcon object

        Returns:
            UUID string, or None if not found
        """
        try:
            return vcon.uuid
        except Exception as e:
            logger.warning(f"Error extracting UUID from vCon: {e}")
            return None

    def extract_identifier(self, vcon: Vcon, s3_key: Optional[str] = None) -> str:
        """
        Extract identifier for deduplication (UUID or S3 key).

        Args:
            vcon: Vcon object
            s3_key: Optional S3 key to use as fallback

        Returns:
            Identifier string
        """
        uuid = self.extract_uuid(vcon)
        if uuid:
            return uuid
        elif s3_key:
            return s3_key
        else:
            # Fallback to a hash or timestamp
            import hashlib
            vcon_json = vcon.to_json()
            return hashlib.md5(vcon_json.encode()).hexdigest()

    def _is_jws_format(self, data: Dict[str, Any]) -> bool:
        """
        Check if data is in JWS (signed) format.

        Args:
            data: Data dictionary

        Returns:
            True if JWS format
        """
        return isinstance(data, dict) and "payload" in data and "signatures" in data

    def _is_jwe_format(self, data: Dict[str, Any]) -> bool:
        """
        Check if data is in JWE (encrypted) format.

        Args:
            data: Data dictionary

        Returns:
            True if JWE format
        """
        return isinstance(data, dict) and "ciphertext" in data and "encrypted_key" in data

    def _migrate_vcon(self, vcon: Vcon, uuid: str) -> Vcon:
        """
        Log the 0.4.0 -> 0.5.0 migration the library applied on load, if any.

        vcon-lib 1.x migrates an unsigned 0.4.0 vCon to 0.5.0 when it is
        built from JSON (``vcon.migration_report`` holds what was inferred
        or left unresolved). A signed 0.4.0 vCon is kept signed and is not
        migrated.

        Args:
            vcon: Vcon object (already migrated by the library if needed)
            uuid: vCon UUID for logging

        Returns:
            The same Vcon object
        """
        try:
            report = getattr(vcon, "migration_report", None)
            if report is not None:
                logger.info(f"vCon {uuid} migrated to 0.5.0: {report.summary()}")
            else:
                current_version = getattr(vcon, "vcon", None)
                logger.debug(f"No migration needed: uuid={uuid}, version={current_version}")
            return vcon
        except Exception as e:
            logger.warning(f"Could not read migration report for vCon {uuid}: {e}")
            return vcon

    def payload_for(self, vcon_data: Dict[str, Any], vcon: Optional[Vcon]) -> Dict[str, Any]:
        """
        Return the document to POST for a loaded vCon.

        The original S3 document, unless ``migrate_version`` is on and the
        library migrated it from 0.4.0 on load, in which case the migrated
        0.5.0 form. Signed and encrypted vCons are always sent unchanged.

        Args:
            vcon_data: The vCon document as read from S3
            vcon: The loaded Vcon object

        Returns:
            The dictionary to POST
        """
        if not self.migrate_version or vcon is None:
            return vcon_data
        if self._is_jws_format(vcon_data) or self._is_jwe_format(vcon_data):
            return self.preserve_security_form(vcon_data)
        if getattr(vcon, "migration_report", None) is None:
            return vcon_data
        return vcon.to_dict()

    def preserve_security_form(self, vcon_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preserve security form (signed/encrypted) without modification.

        Args:
            vcon_data: vCon data dictionary

        Returns:
            Original data (preserved)
        """
        # For signed/encrypted vCons, we return the data as-is
        # This ensures we don't modify the security form
        return vcon_data


import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionService:
    """AES-256-GCM field encryption helper."""

    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("Encryption key must be 32 bytes for AES-256-GCM")
        self._key = key

    def encrypt(self, value: Optional[str]) -> Optional[bytes]:
        if value is None:
            return None
        aes = AESGCM(self._key)
        nonce = os.urandom(12)
        ciphertext = aes.encrypt(nonce, value.encode("utf-8"), None)
        return nonce + ciphertext

    def decrypt(self, payload: Optional[bytes]) -> Optional[str]:
        if payload is None:
            return None
        if len(payload) < 13:
            raise ValueError("Encrypted payload too short")
        nonce, ciphertext = payload[:12], payload[12:]
        aes = AESGCM(self._key)
        plaintext = aes.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def mask(self, value: Optional[str], visible: int = 4) -> Optional[str]:
        if value is None:
            return None
        if len(value) <= visible:
            return value
        return value[:visible] + "***"

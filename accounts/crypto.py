import base64
import os

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class PinDecryptionError(Exception):
    """Raised when an encrypted PIN cannot be decrypted (bad/forged ciphertext)."""


def _load_private_key():
    raw = getattr(settings, "PIN_RSA_PRIVATE_KEY", None)
    if not raw:
        raise ImproperlyConfigured("PIN_RSA_PRIVATE_KEY is not configured.")

    raw = raw.strip()

    # Allow pointing to a file path instead of an inline value.
    if os.path.exists(raw):
        with open(raw, "rb") as f:
            pem = f.read()
    elif "-----BEGIN" in raw:
        pem = raw.encode()
    else:
        # Treat as base64-encoded PEM (single-line, .env friendly).
        try:
            pem = base64.b64decode(raw)
        except Exception as exc:  # noqa: BLE001
            raise ImproperlyConfigured(
                "PIN_RSA_PRIVATE_KEY is not valid base64 or PEM."
            ) from exc

    try:
        return serialization.load_pem_private_key(pem, password=None)
    except Exception as exc:  # noqa: BLE001
        raise ImproperlyConfigured("Failed to load PIN_RSA_PRIVATE_KEY.") from exc


def decrypt_pin(ciphertext_b64: str) -> str:
    """Decrypt an RSA-OAEP/base64 encrypted PIN and return the plaintext."""
    if not ciphertext_b64:
        raise PinDecryptionError("Empty ciphertext.")

    try:
        cipher_bytes = base64.b64decode(ciphertext_b64)
    except Exception as exc:  # noqa: BLE001
        raise PinDecryptionError("Ciphertext is not valid base64.") from exc

    try:
        private_key = _load_private_key()
        plain_bytes = private_key.decrypt(
            cipher_bytes,
            padding.OAEP(
                mgf=padding.MGF1(hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except InvalidKey as exc:
        raise PinDecryptionError("Invalid ciphertext.") from exc
    except Exception as exc:  # noqa: BLE001
        raise PinDecryptionError("Failed to decrypt PIN.") from exc

    try:
        return plain_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PinDecryptionError("Decrypted value is not valid text.") from exc


def encrypt_pin(plain: str) -> str:
    """Encrypt a PIN with the public key derived from the configured private key.

    Used by tests/backend tooling. The mobile app uses its own copy of the
    public key, so this is not required at runtime for client requests.
    """
    private_key = _load_private_key()
    public_key = private_key.public_key()
    cipher_bytes = public_key.encrypt(
        str(plain).encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(cipher_bytes).decode("ascii")

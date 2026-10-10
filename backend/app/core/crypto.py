import base64
import binascii

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


class InvalidPublicKey(ValueError):
    pass


def load_public_key(pem: str) -> ec.EllipticCurvePublicKey:
    try:
        key = serialization.load_pem_public_key(pem.encode())
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise InvalidPublicKey("Clé publique illisible") from exc

    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise InvalidPublicKey("La clé doit être une clé ECDSA P-256")
    return key


def normalize_public_key(pem: str) -> str:
    key = load_public_key(pem)
    return key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def verify_signature(public_key_pem: str, message: bytes, signature_b64: str) -> bool:
    try:
        key = load_public_key(public_key_pem)
        signature = base64.b64decode(signature_b64, validate=True)
        key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidPublicKey, InvalidSignature, binascii.Error, ValueError):
        return False
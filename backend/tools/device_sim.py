"""Simulateur de téléphone EchoShield.

Remplace l'application mobile pendant les tests : il génère la paire de clés
d'un appareil et signe les réponses. À utiliser uniquement en développement.
"""

import argparse
import base64
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

KEYS_DIR = Path(__file__).parent / "keys"


def _key_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "-_")
    if not safe:
        sys.exit("Nom invalide : utilisez des lettres, des chiffres, - ou _")
    return KEYS_DIR / f"{safe}.pem"


def _load_private_key(name: str) -> ec.EllipticCurvePrivateKey:
    path = _key_path(name)
    if not path.exists():
        sys.exit(f"Aucune clé pour « {name} ». Lancez d'abord : new {name}")
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def _public_pem(private_key: ec.EllipticCurvePrivateKey) -> str:
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def _print_body(label: str, private_key: ec.EllipticCurvePrivateKey) -> None:
    body = {"name": label, "public_key": _public_pem(private_key)}
    print("\nBody à coller dans POST /api/devices :\n")
    print(json.dumps(body, indent=2, ensure_ascii=False))


def cmd_new(args: argparse.Namespace) -> None:
    path = _key_path(args.name)
    if path.exists():
        sys.exit(f"La clé « {args.name} » existe déjà. Utilisez : body {args.name}")

    KEYS_DIR.mkdir(exist_ok=True)
    private_key = ec.generate_private_key(ec.SECP256R1())
    path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    print(f"Clé privée enregistrée dans {path}")
    _print_body(args.label or args.name, private_key)


def cmd_body(args: argparse.Namespace) -> None:
    _print_body(args.label or args.name, _load_private_key(args.name))


def cmd_sign(args: argparse.Namespace) -> None:
    private_key = _load_private_key(args.name)
    signature = private_key.sign(args.message.encode(), ec.ECDSA(hashes.SHA256()))
    print(base64.b64encode(signature).decode())


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulateur de téléphone EchoShield")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="générer les clés d'un nouvel appareil")
    new.add_argument("name", help="identifiant court, ex. papa-phone")
    new.add_argument("--label", help="nom affiché, ex. \"iPhone de Papa\"")
    new.set_defaults(func=cmd_new)

    body = sub.add_parser("body", help="réafficher le body d'enregistrement")
    body.add_argument("name")
    body.add_argument("--label")
    body.set_defaults(func=cmd_body)

    sign = sub.add_parser("sign", help="signer un message avec la clé de l'appareil")
    sign.add_argument("name")
    sign.add_argument("message")
    sign.set_defaults(func=cmd_sign)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
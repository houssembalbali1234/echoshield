"""Outils partagés par tous les tests EchoShield.

pytest charge ce fichier automatiquement : les « fixtures » définies ici
sont disponibles dans tous les fichiers de test, sans import.
"""

import base64
import os
import uuid
from dataclasses import dataclass

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

API_URL = os.getenv("API_URL", "http://localhost:8000/api")
PASSWORD = "EchoShieldTest2026"


# --------------------------------------------------------------------------
# Objets de test
# --------------------------------------------------------------------------

class ApiUser:
    """Un utilisateur de test : il s'inscrit et se connecte tout seul."""

    def __init__(self, client: httpx.Client, prefix: str, full_name: str):
        self.email = f"{prefix}+{uuid.uuid4().hex[:12]}@test.echoshield.dev"
        self.full_name = full_name

        response = client.post(
            "/auth/register",
            json={"email": self.email, "full_name": full_name, "password": PASSWORD},
        )
        assert response.status_code == 201, response.text
        self.id = response.json()["id"]

        response = client.post("/auth/login", json={"email": self.email, "password": PASSWORD})
        assert response.status_code == 200, response.text
        tokens = response.json()
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens["refresh_token"]

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}


class FakePhone:
    """Un téléphone simulé : il possède sa clé privée et sait signer."""

    def __init__(self):
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_pem = self.private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        self.id: str | None = None

    def register(self, client: httpx.Client, owner: ApiUser, name: str = "Telephone de test") -> dict:
        response = client.post(
            "/devices",
            json={"name": name, "public_key": self.public_pem},
            headers=owner.headers,
        )
        assert response.status_code == 201, response.text
        self.id = response.json()["id"]
        return response.json()

    def sign(self, message: str) -> str:
        signature = self.private_key.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
        return base64.b64encode(signature).decode()


@dataclass
class Family:
    """Un cercle prêt à l'emploi : Demo (propriétaire, avec téléphone) et Papa (membre)."""

    owner: ApiUser
    member: ApiUser
    circle_id: str
    owner_phone: FakePhone


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def api_is_up():
    """Arrête tout de suite avec un message clair si l'API ne répond pas."""
    try:
        response = httpx.get(f"{API_URL}/health", timeout=5)
    except httpx.HTTPError as exc:
        pytest.exit(f"API injoignable sur {API_URL} : {exc}")
    if response.status_code != 200:
        pytest.exit(f"API en erreur : {response.status_code} {response.text}")


@pytest.fixture
def client():
    with httpx.Client(base_url=API_URL, timeout=10) as c:
        yield c


@pytest.fixture
def make_user(client):
    def _make(prefix: str = "user", full_name: str = "Utilisateur Test") -> ApiUser:
        return ApiUser(client, prefix, full_name)
    return _make


@pytest.fixture
def make_phone():
    return FakePhone


@pytest.fixture
def family(client, make_user) -> Family:
    owner = make_user("owner", "Demo Test")
    member = make_user("member", "Papa Test")

    response = client.post("/circles", json={"name": "Famille Test", "kind": "family"}, headers=owner.headers)
    assert response.status_code == 201, response.text
    circle_id = response.json()["id"]

    response = client.post(f"/circles/{circle_id}/invitations", headers=owner.headers)
    assert response.status_code == 201, response.text
    invite_token = response.json()["token"]

    response = client.post("/invitations/accept", json={"token": invite_token}, headers=member.headers)
    assert response.status_code == 200, response.text

    phone = FakePhone()
    phone.register(client, owner)

    return Family(owner=owner, member=member, circle_id=circle_id, owner_phone=phone)
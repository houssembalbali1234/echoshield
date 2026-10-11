"""Tests de l'authentification : inscription, connexion, jetons."""

from conftest import PASSWORD


def test_inscription_refuse_un_mot_de_passe_trop_court(client):
    response = client.post(
        "/auth/register",
        json={"email": "court@test.echoshield.dev", "full_name": "Test", "password": "12345678"},
    )
    assert response.status_code == 422


def test_inscription_ne_renvoie_jamais_le_mot_de_passe(make_user, client):
    user = make_user()
    response = client.get("/auth/me", headers=user.headers)
    body = response.json()
    assert "password" not in body
    assert "password_hash" not in body


def test_inscription_refuse_un_doublon(make_user, client):
    user = make_user()
    response = client.post(
        "/auth/register",
        json={"email": user.email, "full_name": "Doublon", "password": PASSWORD},
    )
    assert response.status_code == 409


def test_connexion_meme_message_pour_mauvais_mot_de_passe_et_email_inconnu(make_user, client):
    user = make_user()

    wrong_password = client.post("/auth/login", json={"email": user.email, "password": "MauvaisMotDePasse2026"})
    unknown_email = client.post("/auth/login", json={"email": "inconnu@test.echoshield.dev", "password": PASSWORD})

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    # Même message : on ne révèle pas si un compte existe.
    assert wrong_password.json() == unknown_email.json()


def test_route_protegee_sans_jeton(client):
    assert client.get("/auth/me").status_code == 401


def test_route_protegee_avec_jeton(make_user, client):
    user = make_user()
    response = client.get("/auth/me", headers=user.headers)
    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_refresh_est_a_usage_unique(make_user, client):
    user = make_user()

    first = client.post("/auth/refresh", json={"refresh_token": user.refresh_token})
    assert first.status_code == 200

    replay = client.post("/auth/refresh", json={"refresh_token": user.refresh_token})
    assert replay.status_code == 401


def test_un_jeton_acces_ne_sert_pas_de_jeton_de_rafraichissement(make_user, client):
    user = make_user()
    response = client.post("/auth/refresh", json={"refresh_token": user.access_token})
    assert response.status_code == 401


def test_logout_revoque_le_jeton_de_rafraichissement(make_user, client):
    user = make_user()

    assert client.post("/auth/logout", json={"refresh_token": user.refresh_token}).status_code == 204
    assert client.post("/auth/refresh", json={"refresh_token": user.refresh_token}).status_code == 401
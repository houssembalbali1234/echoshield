"""Tests du code secret familial."""

from datetime import datetime, timedelta, timezone

CODE = "Jasmin bleu de Djerba"


# --------------------------------------------------------------------------
# Petits outils
# --------------------------------------------------------------------------

def set_code(client, user, circle_id, code=CODE):
    return client.put(f"/circles/{circle_id}/secret-code", json={"code": code}, headers=user.headers)


def get_status(client, user, circle_id):
    return client.get(f"/circles/{circle_id}/secret-code", headers=user.headers)


def check(client, user, circle_id, code):
    return client.post(f"/circles/{circle_id}/secret-code/check", json={"code": code}, headers=user.headers)


# --------------------------------------------------------------------------
# Définir le code
# --------------------------------------------------------------------------

def test_pas_de_code_au_depart(family, client):
    response = get_status(client, family.member, family.circle_id)
    assert response.status_code == 200
    assert response.json()["has_code"] is False


def test_le_premier_code_est_actif_immediatement(family, client):
    response = set_code(client, family.owner, family.circle_id)
    assert response.status_code == 200
    assert response.json()["has_code"] is True
    assert response.json()["pending_change"] is False

    assert check(client, family.member, family.circle_id, CODE).json()["valid"] is True


def test_le_code_n_est_jamais_renvoye(family, client):
    body = set_code(client, family.owner, family.circle_id).json()
    text = str(body).lower()
    assert "jasmin" not in text
    assert "argon2" not in text


def test_un_simple_membre_ne_peut_pas_changer_le_code(family, client):
    assert set_code(client, family.member, family.circle_id).status_code == 403


def test_code_trop_court(family, client):
    assert set_code(client, family.owner, family.circle_id, "abc").status_code == 422
    # 7 caractères, mais un seul une fois les espaces retirés.
    assert set_code(client, family.owner, family.circle_id, "      a").status_code == 400


def test_changement_de_code_attend_24_heures(family, client):
    set_code(client, family.owner, family.circle_id)

    response = set_code(client, family.owner, family.circle_id, "Nouveau code familial")
    body = response.json()
    assert body["pending_change"] is True

    active_from = datetime.fromisoformat(body["pending_active_from"])
    assert active_from > datetime.now(timezone.utc) + timedelta(hours=23)

    # Pendant le délai, l'ancien code reste le seul valable.
    assert check(client, family.member, family.circle_id, CODE).json()["valid"] is True
    assert check(client, family.member, family.circle_id, "Nouveau code familial").json()["valid"] is False


# --------------------------------------------------------------------------
# Vérifier le code
# --------------------------------------------------------------------------

def test_majuscules_accents_et_espaces_ignores(family, client):
    set_code(client, family.owner, family.circle_id, "Café du Port 1987")
    assert check(client, family.member, family.circle_id, "  CAFE   du port 1987 ").json()["valid"] is True


def test_code_faux(family, client):
    set_code(client, family.owner, family.circle_id)
    body = check(client, family.member, family.circle_id, "rose rouge").json()
    assert body["valid"] is False
    assert body["attempts_left"] == 2


def test_blocage_apres_trois_erreurs(family, client):
    set_code(client, family.owner, family.circle_id)

    left = [check(client, family.member, family.circle_id, f"mauvais code {i}").json()["attempts_left"] for i in range(3)]
    assert left == [2, 1, 0]

    # Même le bon code est refusé pendant le blocage.
    assert check(client, family.member, family.circle_id, CODE).status_code == 429


def test_le_blocage_vaut_pour_tout_le_cercle(family, client):
    set_code(client, family.owner, family.circle_id)
    for i in range(3):
        check(client, family.member, family.circle_id, f"mauvais code {i}")

    # L'escroqueur ne peut pas recommencer en appelant un autre membre.
    assert check(client, family.owner, family.circle_id, CODE).status_code == 429


def test_un_bon_code_remet_le_compteur_a_zero(family, client):
    set_code(client, family.owner, family.circle_id)

    check(client, family.member, family.circle_id, "mauvais code")
    assert check(client, family.member, family.circle_id, CODE).json()["valid"] is True
    assert check(client, family.member, family.circle_id, "mauvais code").json()["attempts_left"] == 2


def test_verifier_sans_code_defini(family, client):
    assert check(client, family.member, family.circle_id, CODE).status_code == 400


def test_un_etranger_n_a_pas_acces(family, make_user, client):
    outsider = make_user("outsider")
    assert get_status(client, outsider, family.circle_id).status_code == 404
    assert check(client, outsider, family.circle_id, CODE).status_code == 404
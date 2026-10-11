"""Tests des cercles de confiance et des invitations."""


def test_le_createur_devient_proprietaire(make_user, client):
    owner = make_user("owner")
    response = client.post("/circles", json={"name": "Famille", "kind": "family"}, headers=owner.headers)
    assert response.status_code == 201
    assert response.json()["my_role"] == "owner"


def test_validation_du_cercle(make_user, client):
    owner = make_user("owner")
    too_short = client.post("/circles", json={"name": "A", "kind": "family"}, headers=owner.headers)
    bad_kind = client.post("/circles", json={"name": "Famille", "kind": "amis"}, headers=owner.headers)
    assert too_short.status_code == 422
    assert bad_kind.status_code == 422


def test_un_etranger_ne_voit_pas_le_cercle(family, make_user, client):
    outsider = make_user("outsider")
    response = client.get(f"/circles/{family.circle_id}", headers=outsider.headers)
    # 404 et non 403 : on ne confirme même pas que le cercle existe.
    assert response.status_code == 404


def test_invitation_a_usage_unique(make_user, client):
    owner = make_user("owner")
    guest = make_user("guest")
    other = make_user("other")

    circle_id = client.post("/circles", json={"name": "Famille", "kind": "family"}, headers=owner.headers).json()["id"]
    token = client.post(f"/circles/{circle_id}/invitations", headers=owner.headers).json()["token"]

    first = client.post("/invitations/accept", json={"token": token}, headers=guest.headers)
    second = client.post("/invitations/accept", json={"token": token}, headers=other.headers)

    assert first.status_code == 200
    assert first.json()["my_role"] == "member"
    assert second.status_code == 400


def test_invitation_inventee_refusee(make_user, client):
    user = make_user()
    response = client.post(
        "/invitations/accept",
        json={"token": "jeton-invente-qui-n-existe-pas-1234567890"},
        headers=user.headers,
    )
    assert response.status_code == 400


def test_delai_de_confiance_de_24_heures(family, client):
    response = client.get(f"/circles/{family.circle_id}", headers=family.owner.headers)
    members = {m["user_id"]: m for m in response.json()["members"]}

    assert members[family.owner.id]["is_trusted"] is True
    assert members[family.member.id]["is_trusted"] is False


def test_un_simple_membre_ne_peut_pas_inviter(family, client):
    response = client.post(f"/circles/{family.circle_id}/invitations", headers=family.member.headers)
    assert response.status_code == 403


def test_personne_ne_peut_retirer_le_proprietaire(family, client):
    response = client.delete(
        f"/circles/{family.circle_id}/members/{family.owner.id}",
        headers=family.member.headers,
    )
    assert response.status_code == 400


def test_un_membre_peut_quitter_le_cercle(family, client):
    leave = client.delete(
        f"/circles/{family.circle_id}/members/{family.member.id}",
        headers=family.member.headers,
    )
    after = client.get(f"/circles/{family.circle_id}", headers=family.member.headers)

    assert leave.status_code == 204
    assert after.status_code == 404
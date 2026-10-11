"""Tests de la vérification hors canal et des attaques contre elle.

Scénario de base : Papa (member) reçoit un appel qui prétend venir de Demo (owner).
Il lance une vérification ; le vrai téléphone de Demo doit signer la réponse.
"""


# --------------------------------------------------------------------------
# Petits outils
# --------------------------------------------------------------------------

def create_verification(client, requester, claimed, circle_id, note="Demande 2000 euros urgent"):
    response = client.post(
        "/verifications",
        json={"circle_id": circle_id, "claimed_user_id": claimed.id, "note": note},
        headers=requester.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def get_challenge(client, claimed, verification_id):
    response = client.get("/verifications/incoming", headers=claimed.headers)
    assert response.status_code == 200, response.text
    for challenge in response.json():
        if challenge["id"] == verification_id:
            return challenge
    raise AssertionError("Défi introuvable dans /verifications/incoming")


def respond(client, user, verification_id, device_id, decision, signature):
    return client.post(
        f"/verifications/{verification_id}/respond",
        json={"device_id": device_id, "decision": decision, "signature": signature},
        headers=user.headers,
    )


# --------------------------------------------------------------------------
# Le scénario normal
# --------------------------------------------------------------------------

def test_le_vrai_telephone_confirme(family, client):
    vid = create_verification(client, family.member, family.owner, family.circle_id)
    challenge = get_challenge(client, family.owner, vid)
    signature = family.owner_phone.sign(challenge["message_to_sign_confirm"])

    response = respond(client, family.owner, vid, family.owner_phone.id, "confirm", signature)
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    # Papa voit le résultat.
    seen_by_requester = client.get(f"/verifications/{vid}", headers=family.member.headers)
    assert seen_by_requester.json()["status"] == "confirmed"


def test_le_vrai_telephone_signale_une_arnaque(family, client):
    vid = create_verification(client, family.member, family.owner, family.circle_id)
    challenge = get_challenge(client, family.owner, vid)
    signature = family.owner_phone.sign(challenge["message_to_sign_deny"])

    response = respond(client, family.owner, vid, family.owner_phone.id, "deny", signature)
    assert response.status_code == 200
    assert response.json()["status"] == "denied"


def test_le_demandeur_ne_voit_jamais_le_defi(family, client):
    vid = create_verification(client, family.member, family.owner, family.circle_id)

    own_request = client.get(f"/verifications/{vid}", headers=family.member.headers).json()
    assert "nonce" not in own_request
    assert "message_to_sign_confirm" not in own_request

    # Le défi n'apparaît que chez la personne censée appeler.
    incoming_for_requester = client.get("/verifications/incoming", headers=family.member.headers).json()
    assert all(c["id"] != vid for c in incoming_for_requester)


# --------------------------------------------------------------------------
# Les attaques
# --------------------------------------------------------------------------

def test_attaque_rejouer_une_reponse(family, client):
    vid = create_verification(client, family.member, family.owner, family.circle_id)
    challenge = get_challenge(client, family.owner, vid)
    signature = family.owner_phone.sign(challenge["message_to_sign_confirm"])

    assert respond(client, family.owner, vid, family.owner_phone.id, "confirm", signature).status_code == 200
    assert respond(client, family.owner, vid, family.owner_phone.id, "confirm", signature).status_code == 409


def test_attaque_signature_copiee_sur_une_autre_demande(family, client):
    first = create_verification(client, family.member, family.owner, family.circle_id)
    second = create_verification(client, family.member, family.owner, family.circle_id)
    old_signature = family.owner_phone.sign(get_challenge(client, family.owner, first)["message_to_sign_confirm"])

    response = respond(client, family.owner, second, family.owner_phone.id, "confirm", old_signature)
    assert response.status_code == 400

    # La signature fausse n'a pas consommé le défi : le vrai téléphone peut encore répondre.
    good_signature = family.owner_phone.sign(get_challenge(client, family.owner, second)["message_to_sign_confirm"])
    assert respond(client, family.owner, second, family.owner_phone.id, "confirm", good_signature).status_code == 200


def test_attaque_transformer_un_non_en_oui(family, client):
    vid = create_verification(client, family.member, family.owner, family.circle_id)
    deny_signature = family.owner_phone.sign(get_challenge(client, family.owner, vid)["message_to_sign_deny"])

    response = respond(client, family.owner, vid, family.owner_phone.id, "confirm", deny_signature)
    assert response.status_code == 400


def test_attaque_signature_avec_une_autre_cle(family, client, make_phone):
    vid = create_verification(client, family.member, family.owner, family.circle_id)
    challenge = get_challenge(client, family.owner, vid)

    attacker_phone = make_phone()  # clé jamais enregistrée
    forged = attacker_phone.sign(challenge["message_to_sign_confirm"])

    response = respond(client, family.owner, vid, family.owner_phone.id, "confirm", forged)
    assert response.status_code == 400


def test_attaque_appareil_revoque(family, client):
    vid = create_verification(client, family.member, family.owner, family.circle_id)
    challenge = get_challenge(client, family.owner, vid)

    revoke = client.delete(f"/devices/{family.owner_phone.id}", headers=family.owner.headers)
    assert revoke.status_code == 204

    signature = family.owner_phone.sign(challenge["message_to_sign_confirm"])
    response = respond(client, family.owner, vid, family.owner_phone.id, "confirm", signature)
    assert response.status_code == 403


def test_attaque_nouvel_appareil_dans_son_delai_de_24_heures(family, client, make_phone):
    vid = create_verification(client, family.member, family.owner, family.circle_id)
    challenge = get_challenge(client, family.owner, vid)

    new_phone = make_phone()
    registered = new_phone.register(client, family.owner, "Telephone de l'attaquant")
    assert registered["can_confirm"] is False

    signature = new_phone.sign(challenge["message_to_sign_confirm"])
    response = respond(client, family.owner, vid, new_phone.id, "confirm", signature)
    assert response.status_code == 403


def test_un_nouveau_membre_peut_dire_non_mais_pas_oui(family, client, make_phone):
    # Rôles inversés : Demo demande à vérifier un appel de Papa, membre depuis moins de 24 h.
    papa_phone = make_phone()
    papa_phone.register(client, family.member, "Telephone de Papa")

    confirm_vid = create_verification(client, family.owner, family.member, family.circle_id)
    confirm_signature = papa_phone.sign(get_challenge(client, family.member, confirm_vid)["message_to_sign_confirm"])
    assert respond(client, family.member, confirm_vid, papa_phone.id, "confirm", confirm_signature).status_code == 403

    deny_vid = create_verification(client, family.owner, family.member, family.circle_id)
    deny_signature = papa_phone.sign(get_challenge(client, family.member, deny_vid)["message_to_sign_deny"])
    response = respond(client, family.member, deny_vid, papa_phone.id, "deny", deny_signature)
    assert response.status_code == 200
    assert response.json()["status"] == "denied"


# --------------------------------------------------------------------------
# Les règles de création
# --------------------------------------------------------------------------

def test_on_ne_peut_pas_se_verifier_soi_meme(family, client):
    response = client.post(
        "/verifications",
        json={"circle_id": family.circle_id, "claimed_user_id": family.member.id},
        headers=family.member.headers,
    )
    assert response.status_code == 400


def test_un_etranger_ne_peut_pas_lancer_de_verification(family, make_user, client):
    outsider = make_user("outsider")
    response = client.post(
        "/verifications",
        json={"circle_id": family.circle_id, "claimed_user_id": family.owner.id},
        headers=outsider.headers,
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# L'historique
# --------------------------------------------------------------------------

def history_ids(client, user, role="all", limit=None):
    params = {"role": role}
    if limit is not None:
        params["limit"] = limit
    response = client.get("/verifications", params=params, headers=user.headers)
    assert response.status_code == 200, response.text
    return [v["id"] for v in response.json()]


def test_historique_envoye_et_recu(family, client):
    first = create_verification(client, family.member, family.owner, family.circle_id)
    second = create_verification(client, family.member, family.owner, family.circle_id)

    # Papa a envoyé les deux demandes, la plus récente en premier.
    assert history_ids(client, family.member, "sent") == [second, first]
    assert history_ids(client, family.member, "received") == []

    # Demo les a reçues.
    assert history_ids(client, family.owner, "received") == [second, first]
    assert history_ids(client, family.owner, "sent") == []

    # « all » regroupe les deux.
    assert history_ids(client, family.member) == [second, first]


def test_historique_contient_statut_et_risque(family, client):
    create_verification(client, family.member, family.owner, family.circle_id, note="2000 euros virement urgent")
    item = client.get("/verifications", headers=family.member.headers).json()[0]
    assert item["status"] == "pending"
    assert item["risk"]["level"] == "high"


def test_historique_limite(family, client):
    for _ in range(3):
        create_verification(client, family.member, family.owner, family.circle_id)
    assert len(history_ids(client, family.member, limit=2)) == 2


def test_historique_role_invalide(family, client):
    response = client.get("/verifications", params={"role": "tout"}, headers=family.member.headers)
    assert response.status_code == 422


def test_un_etranger_ne_voit_rien_dans_l_historique(family, make_user, client):
    create_verification(client, family.member, family.owner, family.circle_id)
    outsider = make_user("outsider")
    assert history_ids(client, outsider) == []
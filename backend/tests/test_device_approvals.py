"""Tests de la récupération : faire valider un nouveau téléphone par deux proches.

Scénario : Papa a perdu son téléphone. Son ancien appareil est révoqué et le
nouveau est dans son délai de 24 h. Demo et Maman, chacun propriétaire d'un
cercle où se trouve Papa (donc membres de confiance), peuvent le valider.
"""

from types import SimpleNamespace

import pytest


def approval_message(device_id, approver_id):
    return f"echoshield:v1:approve-device:{device_id}:{approver_id}"


def create_circle_with(client, owner, member):
    circle_id = client.post(
        "/circles", json={"name": f"Cercle de {owner.full_name}", "kind": "family"}, headers=owner.headers
    ).json()["id"]
    token = client.post(f"/circles/{circle_id}/invitations", headers=owner.headers).json()["token"]
    response = client.post("/invitations/accept", json={"token": token}, headers=member.headers)
    assert response.status_code == 200, response.text
    return circle_id


def approve(client, approver, approver_phone, device_id, signature=None):
    if signature is None:
        signature = approver_phone.sign(approval_message(device_id, approver.id))
    return client.post(
        f"/devices/{device_id}/approvals",
        json={"approver_device_id": approver_phone.id, "signature": signature},
        headers=approver.headers,
    )


def papa_new_phone_can_confirm(client, scene):
    devices = client.get("/devices", headers=scene.papa.headers).json()
    return next(d for d in devices if d["id"] == scene.new_phone.id)["can_confirm"]


@pytest.fixture
def scene(client, make_user, make_phone):
    papa = make_user("papa", "Papa Test")
    demo = make_user("demo", "Demo Test")
    maman = make_user("maman", "Maman Test")

    circle_demo = create_circle_with(client, demo, papa)
    create_circle_with(client, maman, papa)

    demo_phone = make_phone()
    demo_phone.register(client, demo, "Telephone de Demo")
    maman_phone = make_phone()
    maman_phone.register(client, maman, "Telephone de Maman")

    # Papa perd son téléphone : l'ancien est révoqué, le nouveau attend 24 h.
    old_phone = make_phone()
    old_phone.register(client, papa, "Ancien telephone de Papa")
    assert client.delete(f"/devices/{old_phone.id}", headers=papa.headers).status_code == 204

    new_phone = make_phone()
    assert new_phone.register(client, papa, "Nouveau telephone de Papa")["can_confirm"] is False

    return SimpleNamespace(
        papa=papa, demo=demo, maman=maman,
        demo_phone=demo_phone, maman_phone=maman_phone,
        old_phone=old_phone, new_phone=new_phone,
        circle_demo=circle_demo,
    )


# --------------------------------------------------------------------------
# Le scénario normal
# --------------------------------------------------------------------------

def test_deux_validations_activent_le_nouveau_telephone(scene, client):
    first = approve(client, scene.demo, scene.demo_phone, scene.new_phone.id)
    assert first.status_code == 200
    assert first.json()["approvals"] == 1
    assert first.json()["can_confirm"] is False

    second = approve(client, scene.maman, scene.maman_phone, scene.new_phone.id)
    assert second.status_code == 200
    assert second.json()["approvals"] == 2
    assert second.json()["can_confirm"] is True

    assert papa_new_phone_can_confirm(client, scene) is True


def test_une_seule_validation_ne_suffit_pas(scene, client):
    assert approve(client, scene.demo, scene.demo_phone, scene.new_phone.id).status_code == 200
    assert papa_new_phone_can_confirm(client, scene) is False


# --------------------------------------------------------------------------
# Les attaques
# --------------------------------------------------------------------------

def test_on_ne_peut_pas_valider_son_propre_appareil(scene, client):
    response = approve(client, scene.papa, scene.new_phone, scene.new_phone.id)
    assert response.status_code == 403


def test_la_meme_personne_ne_compte_qu_une_fois(scene, client):
    assert approve(client, scene.demo, scene.demo_phone, scene.new_phone.id).status_code == 200
    assert approve(client, scene.demo, scene.demo_phone, scene.new_phone.id).status_code == 409
    assert papa_new_phone_can_confirm(client, scene) is False


def test_un_inconnu_ne_peut_pas_valider(scene, client, make_user, make_phone):
    stranger = make_user("stranger", "Inconnu")
    stranger_phone = make_phone()
    stranger_phone.register(client, stranger)

    response = approve(client, stranger, stranger_phone, scene.new_phone.id)
    assert response.status_code == 404


def test_un_membre_trop_recent_ne_compte_pas(scene, client, make_user, make_phone):
    # Tonton vient d'entrer dans le cercle de Demo : il n'est pas encore de confiance.
    tonton = make_user("tonton", "Tonton Test")
    token = client.post(f"/circles/{scene.circle_demo}/invitations", headers=scene.demo.headers).json()["token"]
    client.post("/invitations/accept", json={"token": token}, headers=tonton.headers)
    tonton_phone = make_phone()
    tonton_phone.register(client, tonton)

    response = approve(client, tonton, tonton_phone, scene.new_phone.id)
    assert response.status_code == 404


def test_signature_copiee_pour_un_autre_appareil(scene, client):
    signature_for_old_phone = scene.demo_phone.sign(approval_message(scene.old_phone.id, scene.demo.id))
    response = approve(client, scene.demo, scene.demo_phone, scene.new_phone.id, signature_for_old_phone)
    assert response.status_code == 400


def test_telephone_du_valideur_pas_encore_autorise(scene, client, make_phone):
    # Le deuxième téléphone de Demo est lui-même dans son délai de 24 h.
    demo_second_phone = make_phone()
    demo_second_phone.register(client, scene.demo, "Deuxieme telephone de Demo")

    response = approve(client, scene.demo, demo_second_phone, scene.new_phone.id)
    assert response.status_code == 403


def test_un_appareil_revoque_ne_peut_pas_etre_valide(scene, client):
    response = approve(client, scene.demo, scene.demo_phone, scene.old_phone.id)
    assert response.status_code == 400
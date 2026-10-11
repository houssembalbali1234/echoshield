"""Tests du moteur de risque.

La plupart testent le moteur directement (sans l'API) : c'est instantané.
Les derniers vérifient l'intégration dans l'API.
"""

from app.services.risk import RiskLevel, analyze, normalize


def codes(report):
    return {signal.code for signal in report.signals}


# --------------------------------------------------------------------------
# Le moteur seul
# --------------------------------------------------------------------------

def test_texte_vide_risque_faible():
    assert analyze("").level == RiskLevel.LOW
    assert analyze(None).score == 0


def test_message_ordinaire_risque_faible():
    report = analyze("Je serai en retard pour le diner ce soir")
    assert report.level == RiskLevel.LOW
    assert report.signals == []


def test_arnaque_classique_en_francais():
    report = analyze("Papa c'est moi, j'ai besoin de 2000 euros par virement, c'est urgent")
    assert report.level == RiskLevel.HIGH
    assert {"money", "urgency", "classic_scam_combo"} <= codes(report)


def test_arnaque_en_anglais():
    report = analyze("Mom I lost my phone, this is my new number. Please send money, don't tell dad")
    assert report.level == RiskLevel.HIGH
    assert {"distress", "money", "secrecy"} <= codes(report)


def test_arnaque_en_arabe_avec_voyelles():
    # « فوراً » porte un signe diacritique : la normalisation doit le retirer.
    report = analyze("ابعثلي فلوس فوراً")
    assert report.level == RiskLevel.HIGH
    assert {"money", "urgency"} <= codes(report)


def test_fraude_au_president():
    report = analyze(
        "Je suis le directeur, operation confidentielle : faites un virement vers le nouveau RIB"
    )
    assert report.level == RiskLevel.HIGH
    assert report.score == 100
    assert {"authority", "secrecy", "money", "new_beneficiary"} <= codes(report)


def test_cartes_cadeaux_risque_moyen():
    report = analyze("Achete des cartes cadeaux Google Play")
    assert report.level == RiskLevel.MEDIUM
    assert "risky_payment" in codes(report)


def test_demande_de_code_sms():
    report = analyze("Donne-moi le code SMS que tu viens de recevoir")
    assert "credentials" in codes(report)
    assert report.level == RiskLevel.MEDIUM


def test_pas_de_faux_positif_vite_dans_invite():
    report = analyze("Je t'invite au restaurant samedi")
    assert report.signals == []


def test_majuscules_et_accents_reconnus():
    report = analyze("URGENT : VIREMENT IMMÉDIATEMENT")
    assert {"urgency", "money"} <= codes(report)


def test_chaque_signal_est_explique():
    report = analyze("Envoie 500 euros en bitcoin tout de suite, c'est secret")
    for signal in report.signals:
        assert signal.label
        if signal.code != "classic_scam_combo":
            assert signal.matches, f"{signal.code} sans mot déclencheur"


def test_normalisation():
    assert normalize("  Téléphone   CASSÉ ") == "telephone casse"
    assert normalize("فوراً") == "فورا"


# --------------------------------------------------------------------------
# L'intégration dans l'API
# --------------------------------------------------------------------------

def test_route_analyse_exige_une_connexion(client):
    response = client.post("/risk/analyze", json={"text": "virement urgent"})
    assert response.status_code == 401


def test_route_analyse(make_user, client):
    user = make_user()
    response = client.post(
        "/risk/analyze",
        json={"text": "J'ai besoin de 2000 euros par virement, c'est urgent"},
        headers=user.headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "high"
    assert body["recommendation"]


def test_chaque_verification_contient_son_analyse_de_risque(family, client):
    response = client.post(
        "/verifications",
        json={
            "circle_id": family.circle_id,
            "claimed_user_id": family.owner.id,
            "note": "Demo demande 2000 euros par virement urgent",
        },
        headers=family.member.headers,
    )
    assert response.status_code == 201
    assert response.json()["risk"]["level"] == "high"
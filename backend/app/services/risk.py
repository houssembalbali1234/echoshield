"""Moteur de risque d'EchoShield.

Règles déterministes, sans IA : à texte identique, résultat identique,
et chaque alerte est expliquée. Langues couvertes : français, anglais, arabe.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class Rule:
    code: str
    label: str
    weight: int
    patterns: tuple[str, ...]


@dataclass
class Signal:
    code: str
    label: str
    weight: int
    matches: list[str] = field(default_factory=list)


@dataclass
class RiskReport:
    level: RiskLevel
    score: int
    signals: list[Signal]
    recommendation: str


# --------------------------------------------------------------------------
# Les règles. Les motifs s'appliquent au texte normalisé :
# minuscules, sans accents, sans signes diacritiques arabes.
# --------------------------------------------------------------------------

AMOUNT = r"\d[\d\s.,]*\s?(?:€|euros?|dt|tnd|dinars?|aed|dirhams?|dhs?|usd|dollars?|\$)"

RULES: tuple[Rule, ...] = (
    Rule(
        code="urgency",
        label="Urgence ou pression sur le temps",
        weight=20,
        patterns=(
            r"\burgen(?:t|te|ce|tly|cy)\b", r"\btout de suite\b", r"\bimmediatement\b",
            r"\bmaintenant\b", r"\bvite\b", r"\bsans attendre\b", r"\bdans l'heure\b",
            r"\bright now\b", r"\bimmediately\b", r"\basap\b", r"\bas soon as possible\b", r"\bhurry\b",
            r"\bعاجل\b", r"\bفورا\b", r"\bحالا\b", r"\bبسرع[ةه]\b", r"\bالان\b",
        ),
    ),
    Rule(
        code="money",
        label="Demande d'argent ou de paiement",
        weight=25,
        patterns=(
            AMOUNT, r"\bvirement\b", r"\bvirer\b", r"\btransf[eé]r(?:er|t)?\b", r"\bargent\b",
            r"\bpa(?:yer|iement)\b", r"\brembourser\b", r"\bmontant\b",
            r"\bwire\b", r"\bsend money\b", r"\bpayment\b", r"\bpay\b", r"\btransfer\b",
            r"\bتحويل\b", r"\bحوال[ةه]\b", r"\bفلوس\b", r"\b(?:ال)?مال\b", r"\bادفع\b", r"\bدفع\b",
        ),
    ),
    Rule(
        code="secrecy",
        label="Demande de secret ou de discrétion",
        weight=25,
        patterns=(
            r"\bne (?:le |la |lui |leur )?(?:dis|dites) (?:rien|pas)\b", r"\bn'en parle", r"\bgarde (?:ca|le|cela) pour toi\b",
            r"\bentre nous\b", r"\bsecret(?:e|ement)?\b", r"\bpersonne ne doit (?:le )?savoir\b", r"\bconfidentiel(?:le)?\b",
            r"\bdon'?t tell\b", r"\bkeep (?:it|this) (?:secret|quiet|between us)\b", r"\bbetween us\b", r"\bconfidential\b",
            r"\bسر\b", r"\bلا تخبر", r"\bلا تقل", r"\bبيني وبينك\b",
        ),
    ),
    Rule(
        code="risky_payment",
        label="Moyen de paiement difficile à récupérer",
        weight=30,
        patterns=(
            r"\bcartes? cadeaux?\b", r"\bgift ?cards?\b", r"\bitunes\b", r"\bgoogle play\b", r"\bsteam\b",
            r"\bbitcoin\b", r"\bcrypto\w*\b", r"\busdt\b", r"\bbinance\b", r"\bwestern union\b",
            r"\bmoneygram\b", r"\bmandat cash\b", r"\btranscash\b", r"\bneosurf\b", r"\bpcs\b",
            r"\bبطاق[ةه] هدي[ةه]\b", r"\bبيتكوين\b", r"\bعمل[ةه] رقمي[ةه]\b",
        ),
    ),
    Rule(
        code="new_beneficiary",
        label="Nouveau bénéficiaire ou changement de coordonnées bancaires",
        weight=30,
        patterns=(
            r"\bnouve(?:au|l) (?:rib|iban|compte|beneficiaire)\b", r"\bchangement de (?:rib|iban|compte)\b",
            r"\bautre compte\b", r"\bcoordonnees bancaires\b",
            r"\bnew (?:account|bank details|beneficiary|iban)\b", r"\bchanged? (?:my )?bank details\b",
            r"\bحساب جديد\b",
        ),
    ),
    Rule(
        code="distress",
        label="Situation de détresse ou changement de numéro",
        weight=15,
        patterns=(
            r"\baccident\b", r"\bhopital\b", r"\bpolice\b", r"\bprison\b", r"\bgarde a vue\b",
            r"\bavocat\b", r"\bcaution\b", r"\bamende\b", r"\brancon\b",
            r"\btelephone (?:casse|perdu|vole)\b", r"\bnouveau numero\b",
            r"\bhospital\b", r"\bjail\b", r"\barrested\b", r"\blawyer\b", r"\bbail\b",
            r"\blost my phone\b", r"\bnew number\b",
            r"\bحادث\b", r"\bمستشفي\b", r"\bشرط[ةه]\b", r"\bسجن\b", r"\bمحامي\b", r"\bرقم جديد\b",
        ),
    ),
    Rule(
        code="credentials",
        label="Demande de code, de mot de passe ou d'identifiant",
        weight=35,
        patterns=(
            r"\bcode (?:sms|de verification|recu|pin)\b", r"\bmot de passe\b", r"\botp\b", r"\bidentifiants?\b",
            r"\bverification code\b", r"\bpassword\b", r"\bpin code\b", r"\bone[- ]time code\b",
            r"\bكلم[ةه] (?:السر|المرور)\b", r"\bرمز التحقق\b", r"\bالكود\b",
        ),
    ),
    Rule(
        code="authority",
        label="Pression d'une autorité (dirigeant, banque, administration)",
        weight=15,
        patterns=(
            r"\bpatron\b", r"\bdirect(?:eur|rice)\b", r"\bpdg\b", r"\bpresident\b", r"\bta banque\b", r"\bvotre banque\b",
            r"\bceo\b", r"\bboss\b", r"\bdirector\b", r"\byour bank\b",
            r"\bالمدير\b", r"\bالبنك\b",
        ),
    ),
)

COMBO = Signal(
    code="classic_scam_combo",
    label="Combinaison classique d'arnaque : argent demandé avec urgence ou secret",
    weight=15,
)

THRESHOLD_HIGH = 60
THRESHOLD_MEDIUM = 30

RECOMMENDATIONS = {
    RiskLevel.LOW: "Peu de signaux d'arnaque. En cas de doute, vérifiez quand même.",
    RiskLevel.MEDIUM: "Signaux suspects : vérifiez l'identité avant d'agir.",
    RiskLevel.HIGH: "Fort risque d'arnaque : ne faites rien avant une vérification confirmée.",
}

_COMPILED = [(rule, re.compile("|".join(rule.patterns))) for rule in RULES]


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("ى", "ي")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip()


def analyze(text: str | None) -> RiskReport:
    if not text or not text.strip():
        return RiskReport(RiskLevel.LOW, 0, [], RECOMMENDATIONS[RiskLevel.LOW])

    normalized = normalize(text)
    signals: list[Signal] = []
    for rule, regex in _COMPILED:
        matches = sorted({match.group(0).strip() for match in regex.finditer(normalized)})
        if matches:
            signals.append(Signal(rule.code, rule.label, rule.weight, matches))

    codes = {signal.code for signal in signals}
    if "money" in codes and codes & {"urgency", "secrecy"}:
        signals.append(Signal(COMBO.code, COMBO.label, COMBO.weight))

    score = min(100, sum(signal.weight for signal in signals))
    if score >= THRESHOLD_HIGH:
        level = RiskLevel.HIGH
    elif score >= THRESHOLD_MEDIUM:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    return RiskReport(level, score, signals, RECOMMENDATIONS[level])
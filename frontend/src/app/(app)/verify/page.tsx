"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { useCurrentUser } from "@/components/app-shell";
import { RiskPanel } from "@/components/risk-panel";
import { Alert, Button, Card } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import type { Circle, CircleDetail, Member, RiskReport, Verification } from "@/lib/types";

const SELECT_CLASS =
  "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30";

function formatRemaining(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function VerifyPage() {
  const me = useCurrentUser();

  const [circles, setCircles] = useState<Circle[] | null>(null);
  const [circleId, setCircleId] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [claimedId, setClaimedId] = useState("");
  const [note, setNote] = useState("");
  const [risk, setRisk] = useState<RiskReport | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 1. Mes cercles ; on présélectionne le premier.
  useEffect(() => {
    api<Circle[]>("/circles")
      .then((list) => {
        setCircles(list);
        if (list.length > 0) setCircleId(list[0].id);
      })
      .catch((err) => setError(errorText(err)));
  }, []);

  // 2. Les membres du cercle choisi, sauf moi.
  useEffect(() => {
    if (!circleId) return;
    api<CircleDetail>(`/circles/${circleId}`)
      .then((circle) => {
        const others = circle.members.filter((m) => m.user_id !== me.id);
        setMembers(others);
        setClaimedId(others[0]?.user_id ?? "");
      })
      .catch((err) => setError(errorText(err)));
  }, [circleId, me.id]);

  // 3. Analyse de risque en direct, 500 ms après la dernière frappe.
  const text = note.trim();
  useEffect(() => {
    if (text.length < 3) return;
    const timer = setTimeout(() => {
      api<RiskReport>("/risk/analyze", { method: "POST", body: { text } })
        .then(setRisk)
        .catch(() => {});
    }, 500);
    return () => clearTimeout(timer);
  }, [text]);
  const liveRisk = text.length >= 3 ? risk : null;

  // 4. Tant que la demande est en attente : on suit son statut et le compte à rebours.
  const pendingId = verification?.status === "pending" ? verification.id : null;
  useEffect(() => {
    if (!pendingId) return;
    const poll = setInterval(() => {
      api<Verification>(`/verifications/${pendingId}`)
        .then(setVerification)
        .catch(() => {});
    }, 2000);
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(clock);
    };
  }, [pendingId]);

  async function startVerification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const created = await api<Verification>("/verifications", {
        method: "POST",
        body: { circle_id: circleId, claimed_user_id: claimedId, note: text || null },
      });
      setNow(Date.now());
      setVerification(created);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function startOver() {
    setVerification(null);
    setNote("");
    setRisk(null);
  }

  const claimedName =
    members.find((m) => m.user_id === verification?.claimed_user_id)?.full_name ?? "votre proche";

  // ------------------------------------------------------------------------
  // Écran de résultat
  // ------------------------------------------------------------------------
  if (verification) {
    const remaining = Math.max(0, Math.ceil((new Date(verification.expires_at).getTime() - now) / 1000));
    const highRisk = verification.risk.level === "high";

    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight">Vérification d&apos;un appel</h1>

        {verification.status === "pending" && (
          <Card className="text-center">
            <p className="text-4xl" aria-hidden>⏳</p>
            <p className="mt-3 text-lg font-semibold">En attente de la réponse de {claimedName}…</p>
            <p className="mt-1 text-sm text-slate-600">
              Son téléphone vient de recevoir la demande. Ne faites rien tant qu&apos;il n&apos;a pas répondu.
            </p>
            <p className="mt-4 font-mono text-2xl tabular-nums" aria-live="off">
              {formatRemaining(remaining)}
            </p>
          </Card>
        )}

        {verification.status === "confirmed" && (
          <Alert tone="success">
            <p className="text-base font-semibold">✅ Vérifié : c&apos;est bien {claimedName}.</p>
            <p className="mt-1">Son appareil enregistré a signé la confirmation.</p>
          </Alert>
        )}

        {verification.status === "confirmed" && highRisk && (
          <Alert tone="warning">
            La demande reste à <strong>risque élevé</strong>. Avant tout virement, rappelez {claimedName} sur
            son numéro habituel.
          </Alert>
        )}

        {verification.status === "denied" && (
          <Alert tone="error">
            <p className="text-base font-semibold">⛔ Ce n&apos;est PAS {claimedName}.</p>
            <p className="mt-1">
              {claimedName} affirme depuis son propre appareil ne pas vous appeler. C&apos;est très
              probablement une arnaque : raccrochez et n&apos;envoyez rien.
            </p>
          </Alert>
        )}

        {verification.status === "expired" && (
          <Alert tone="warning">
            <p className="text-base font-semibold">⌛ Pas de réponse : appel NON vérifié.</p>
            <p className="mt-1">
              L&apos;absence de réponse n&apos;est jamais une confirmation. N&apos;agissez pas, et essayez de
              joindre {claimedName} autrement.
            </p>
          </Alert>
        )}

        <RiskPanel report={verification.risk} />

        {verification.status !== "pending" && (
          <Button variant="secondary" onClick={startOver}>
            Nouvelle vérification
          </Button>
        )}
      </div>
    );
  }

  // ------------------------------------------------------------------------
  // Formulaire
  // ------------------------------------------------------------------------
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Vérifier un appel</h1>
        <p className="mt-1 text-sm text-slate-600">
          Un appel vous semble suspect ? Demandez au vrai téléphone de votre proche de confirmer.
        </p>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      {circles === null ? (
        <p className="text-sm text-slate-500">Chargement…</p>
      ) : circles.length === 0 ? (
        <Card className="text-center">
          <p className="font-medium">Vous n&apos;avez pas encore de cercle.</p>
          <p className="mt-1 text-sm text-slate-600">
            <Link href="/circles" className="font-medium text-indigo-700 hover:underline">
              Créez ou rejoignez un cercle
            </Link>{" "}
            pour pouvoir vérifier vos proches.
          </p>
        </Card>
      ) : (
        <Card>
          <form onSubmit={startVerification} className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label htmlFor="circle" className="block text-sm font-medium text-slate-700">
                  Cercle
                </label>
                <select id="circle" value={circleId} onChange={(e) => setCircleId(e.target.value)} className={SELECT_CLASS}>
                  {circles.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="claimed" className="block text-sm font-medium text-slate-700">
                  Qui prétend vous appeler ?
                </label>
                <select
                  id="claimed"
                  value={claimedId}
                  onChange={(e) => setClaimedId(e.target.value)}
                  disabled={members.length === 0}
                  className={SELECT_CLASS}
                >
                  {members.length === 0 ? (
                    <option>Aucun autre membre</option>
                  ) : (
                    members.map((m) => (
                      <option key={m.user_id} value={m.user_id}>
                        {m.full_name}
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="note" className="block text-sm font-medium text-slate-700">
                Que vous demande-t-on ?
              </label>
              <textarea
                id="note"
                rows={3}
                maxLength={500}
                placeholder="Ex. : Il me demande 2 000 € par virement, c'est urgent et je ne dois rien dire à personne."
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
              />
              <p className="text-xs text-slate-500">Facultatif. EchoShield analyse le texte pendant que vous tapez.</p>
            </div>

            {liveRisk && <RiskPanel report={liveRisk} />}

            <Button type="submit" disabled={busy || !claimedId} className="w-full">
              {busy ? "Envoi…" : "Envoyer la demande de vérification"}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
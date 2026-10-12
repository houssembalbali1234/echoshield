"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Alert, Button, Card, Field } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import type { SecretCodeCheckResult, SecretCodeStatus } from "@/lib/types";

function formatDate(iso: string) {
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

type Message = { tone: "error" | "success" | "warning"; text: string };

export function SecretCodeCard({ circleId, canManage }: { circleId: string; canManage: boolean }) {
  const [status, setStatus] = useState<SecretCodeStatus | null>(null);
  const [checkInput, setCheckInput] = useState("");
  const [newCode, setNewCode] = useState("");
  const [checkMessage, setCheckMessage] = useState<Message | null>(null);
  const [setMessage, setSetMessage] = useState<Message | null>(null);
  const [busy, setBusy] = useState<"check" | "set" | null>(null);

  useEffect(() => {
    api<SecretCodeStatus>(`/circles/${circleId}/secret-code`)
      .then(setStatus)
      .catch(() => {});
  }, [circleId]);

  async function check(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("check");
    setCheckMessage(null);
    try {
      const result = await api<SecretCodeCheckResult>(`/circles/${circleId}/secret-code/check`, {
        method: "POST",
        body: { code: checkInput },
      });
      setCheckMessage(
        result.valid
          ? { tone: "success", text: "✅ Code correct. Restez vigilant : un code peut avoir été divulgué." }
          : {
              tone: "error",
              text:
                result.attempts_left > 0
                  ? `⛔ Code incorrect. Encore ${result.attempts_left} essai(s) avant blocage du cercle.`
                  : "⛔ Code incorrect. Le cercle est bloqué pendant 15 minutes.",
            },
      );
      setCheckInput("");
    } catch (err) {
      setCheckMessage({ tone: "error", text: errorText(err) });
    } finally {
      setBusy(null);
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("set");
    setSetMessage(null);
    try {
      const next = await api<SecretCodeStatus>(`/circles/${circleId}/secret-code`, {
        method: "PUT",
        body: { code: newCode },
      });
      setStatus(next);
      setNewCode("");
      setSetMessage(
        next.pending_change && next.pending_active_from
          ? {
              tone: "warning",
              text: `Nouveau code enregistré. Par sécurité, il remplacera l'ancien le ${formatDate(next.pending_active_from)}.`,
            }
          : { tone: "success", text: "Code enregistré. Communiquez-le de vive voix à vos proches." },
      );
    } catch (err) {
      setSetMessage({ tone: "error", text: errorText(err) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <h2 className="font-semibold">Code secret familial</h2>
      <p className="mt-1 text-sm text-slate-600">
        Une phrase que seuls les membres connaissent. En cas d&apos;appel suspect, demandez-la à
        l&apos;appelant.
      </p>

      {status === null ? (
        <p className="mt-4 text-sm text-slate-500">Chargement…</p>
      ) : (
        <div className="mt-5 space-y-6">
          {status.has_code ? (
            <form onSubmit={check} className="space-y-3">
              <Field
                id="check_code"
                label="Vérifier le code donné par l'appelant"
                autoComplete="off"
                required
                value={checkInput}
                onChange={(e) => setCheckInput(e.target.value)}
              />
              {checkMessage && <Alert tone={checkMessage.tone}>{checkMessage.text}</Alert>}
              <Button type="submit" variant="secondary" disabled={busy !== null}>
                {busy === "check" ? "Vérification…" : "Vérifier"}
              </Button>
            </form>
          ) : (
            <Alert tone="info">
              Ce cercle n&apos;a pas encore de code secret.
              {!canManage && " Demandez au propriétaire d'en définir un."}
            </Alert>
          )}

          {status.pending_change && status.pending_active_from && (
            <Alert tone="warning">
              Un nouveau code remplacera l&apos;actuel le {formatDate(status.pending_active_from)}. Si vous
              n&apos;êtes pas à l&apos;origine de ce changement, prévenez le cercle.
            </Alert>
          )}

          {canManage && (
            <form onSubmit={save} className="space-y-3 border-t border-slate-100 pt-5">
              <Field
                id="new_code"
                label={status.has_code ? "Changer le code" : "Définir le code"}
                type="password"
                autoComplete="new-password"
                hint="6 caractères minimum. Une petite phrase est plus sûre qu'un numéro. Majuscules et accents sont ignorés."
                required
                minLength={6}
                maxLength={64}
                value={newCode}
                onChange={(e) => setNewCode(e.target.value)}
              />
              {setMessage && <Alert tone={setMessage.tone}>{setMessage.text}</Alert>}
              <Button type="submit" disabled={busy !== null}>
                {busy === "set" ? "Enregistrement…" : status.has_code ? "Changer le code" : "Définir le code"}
              </Button>
            </form>
          )}
        </div>
      )}
    </Card>
  );
}
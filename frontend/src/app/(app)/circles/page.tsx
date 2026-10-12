"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { Alert, Button, Card, Field } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import type { Circle, CircleKind, CircleRole } from "@/lib/types";

const ROLE_LABELS: Record<CircleRole, string> = {
  owner: "Propriétaire",
  admin: "Administrateur",
  member: "Membre",
};

const KIND_LABELS: Record<CircleKind, string> = {
  family: "Famille",
  enterprise: "Entreprise",
};

export default function CirclesPage() {
  const [circles, setCircles] = useState<Circle[] | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState<"create" | "join" | null>(null);

  const [name, setName] = useState("");
  const [kind, setKind] = useState<CircleKind>("family");
  const [inviteToken, setInviteToken] = useState("");

  // Recharge la liste à l'ouverture, puis chaque fois que « version » change.
  useEffect(() => {
    api<Circle[]>("/circles")
      .then(setCircles)
      .catch((err) => setError(errorText(err)));
  }, [version]);

  async function createCircle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("create");
    setError(null);
    setSuccess(null);
    try {
      await api("/circles", { method: "POST", body: { name, kind } });
      setName("");
      setSuccess("Cercle créé. Vous en êtes le propriétaire.");
      setVersion((v) => v + 1);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function joinCircle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("join");
    setError(null);
    setSuccess(null);
    try {
      await api("/invitations/accept", { method: "POST", body: { token: inviteToken.trim() } });
      setInviteToken("");
      setSuccess("Vous avez rejoint le cercle. Vous serez membre de confiance dans 24 h.");
      setVersion((v) => v + 1);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Mes cercles</h1>
        <p className="mt-1 text-sm text-slate-600">
          Les personnes de confiance qui peuvent vérifier vos appels, et que vous pouvez vérifier.
        </p>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {success && <Alert tone="success">{success}</Alert>}

      {circles === null ? (
        <p className="text-sm text-slate-500">Chargement…</p>
      ) : circles.length === 0 ? (
        <Card className="text-center">
          <p className="font-medium">Vous n&apos;avez pas encore de cercle.</p>
          <p className="mt-1 text-sm text-slate-600">
            Créez-en un pour votre famille, ou rejoignez celui d&apos;un proche avec une invitation.
          </p>
        </Card>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {circles.map((circle) => (
            <li key={circle.id}>
              <Link
                href={`/circles/${circle.id}`}
                className="block rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-indigo-300 hover:shadow"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="font-semibold">{circle.name}</h2>
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                    {KIND_LABELS[circle.kind]}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-600">{ROLE_LABELS[circle.my_role]}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <h2 className="font-semibold">Créer un cercle</h2>
          <form onSubmit={createCircle} className="mt-4 space-y-4">
            <Field
              id="circle_name"
              label="Nom du cercle"
              placeholder="Famille Ben Ali"
              required
              minLength={2}
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <div className="space-y-1.5">
              <label htmlFor="circle_kind" className="block text-sm font-medium text-slate-700">
                Type
              </label>
              <select
                id="circle_kind"
                value={kind}
                onChange={(e) => setKind(e.target.value as CircleKind)}
                className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
              >
                <option value="family">Famille</option>
                <option value="enterprise">Entreprise</option>
              </select>
            </div>
            <Button type="submit" disabled={busy !== null} className="w-full">
              {busy === "create" ? "Création…" : "Créer le cercle"}
            </Button>
          </form>
        </Card>

        <Card>
          <h2 className="font-semibold">Rejoindre un cercle</h2>
          <form onSubmit={joinCircle} className="mt-4 space-y-4">
            <Field
              id="invite_token"
              label="Jeton d'invitation"
              hint="Le propriétaire du cercle vous l'a envoyé. Il est valable 48 h et ne sert qu'une fois."
              required
              minLength={20}
              value={inviteToken}
              onChange={(e) => setInviteToken(e.target.value)}
            />
            <Button type="submit" variant="secondary" disabled={busy !== null} className="w-full">
              {busy === "join" ? "Un instant…" : "Rejoindre"}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
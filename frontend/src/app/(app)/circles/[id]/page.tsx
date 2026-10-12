"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useCurrentUser } from "@/components/app-shell";
import { SecretCodeCard } from "@/components/secret-code-card";
import { Alert, Button, Card } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import type { CircleDetail, CircleRole, Invitation } from "@/lib/types";

const ROLE_LABELS: Record<CircleRole, string> = {
  owner: "Propriétaire",
  admin: "Administrateur",
  member: "Membre",
};

function formatDate(iso: string) {
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

export default function CirclePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const me = useCurrentUser();

  const [circle, setCircle] = useState<CircleDetail | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<CircleDetail>(`/circles/${id}`)
      .then(setCircle)
      .catch((err) => setError(errorText(err)));
  }, [id, version]);

  const canManage = circle?.my_role === "owner" || circle?.my_role === "admin";

  async function invite() {
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      setInvitation(await api<Invitation>(`/circles/${id}/invitations`, { method: "POST" }));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function copyToken() {
    if (!invitation) return;
    try {
      await navigator.clipboard.writeText(invitation.token);
      setCopied(true);
    } catch {
      setError("Copie impossible : sélectionnez le jeton à la main.");
    }
  }

  async function removeMember(userId: string, isMe: boolean) {
    const question = isMe ? "Quitter ce cercle ?" : "Retirer ce membre du cercle ?";
    if (!window.confirm(question)) return;
    try {
      await api(`/circles/${id}/members/${userId}`, { method: "DELETE" });
      if (isMe) router.push("/circles");
      else setVersion((v) => v + 1);
    } catch (err) {
      setError(errorText(err));
    }
  }

  if (error && !circle) return <Alert tone="error">{error}</Alert>;
  if (!circle) return <p className="text-sm text-slate-500">Chargement…</p>;

  return (
    <div className="space-y-8">
      <div>
        <Link href="/circles" className="text-sm text-slate-600 hover:text-slate-900">
          ← Mes cercles
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{circle.name}</h1>
        <p className="mt-1 text-sm text-slate-600">
          {circle.kind === "family" ? "Famille" : "Entreprise"} · vous êtes{" "}
          {ROLE_LABELS[circle.my_role].toLowerCase()}
        </p>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Membres ({circle.members.length})</h2>
          {canManage && (
            <Button onClick={invite} disabled={busy}>
              {busy ? "Un instant…" : "Inviter quelqu'un"}
            </Button>
          )}
        </div>

        {invitation && (
          <div className="mt-4 space-y-3 rounded-xl bg-indigo-50 p-4 ring-1 ring-indigo-200">
            <p className="text-sm text-indigo-900">
              Envoyez ce jeton à la personne à inviter. Il ne sert qu&apos;une fois et expire le{" "}
              {formatDate(invitation.expires_at)}.
            </p>
            <code className="block break-all rounded-lg bg-white px-3 py-2 font-mono text-sm ring-1 ring-indigo-200">
              {invitation.token}
            </code>
            <Button variant="secondary" onClick={copyToken}>
              {copied ? "Copié ✓" : "Copier le jeton"}
            </Button>
          </div>
        )}

        <ul className="mt-4 divide-y divide-slate-100">
          {circle.members.map((member) => {
            const isMe = member.user_id === me.id;
            const canRemove = member.role !== "owner" && (isMe || canManage);
            return (
              <li key={member.user_id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-medium">
                    {member.full_name}
                    {isMe && <span className="font-normal text-slate-500"> (vous)</span>}
                  </p>
                  <p className="text-sm text-slate-600">
                    {member.email} · {ROLE_LABELS[member.role]}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {member.is_trusted ? (
                    <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
                      De confiance
                    </span>
                  ) : (
                    <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">
                      De confiance le {formatDate(member.trusted_from)}
                    </span>
                  )}
                  {canRemove && (
                    <button
                      onClick={() => removeMember(member.user_id, isMe)}
                      className="text-sm font-medium text-rose-600 hover:text-rose-700"
                    >
                      {isMe ? "Quitter" : "Retirer"}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </Card>

      <SecretCodeCard circleId={id} canManage={canManage} />
    </div>
  );
}
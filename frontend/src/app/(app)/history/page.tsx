"use client";

import { useEffect, useState } from "react";

import { useCurrentUser } from "@/components/app-shell";
import { Alert, Card } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import type { RiskLevel, Verification, VerificationStatus } from "@/lib/types";

type Role = "all" | "sent" | "received";

const TABS: { value: Role; label: string }[] = [
  { value: "all", label: "Toutes" },
  { value: "sent", label: "Envoyées" },
  { value: "received", label: "Reçues" },
];

const STATUS: Record<VerificationStatus, { label: string; className: string }> = {
  pending: { label: "⏳ En attente", className: "bg-slate-100 text-slate-700 ring-slate-200" },
  confirmed: { label: "✅ Confirmé", className: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  denied: { label: "⛔ Refusé", className: "bg-rose-50 text-rose-700 ring-rose-200" },
  expired: { label: "⌛ Expiré", className: "bg-amber-50 text-amber-800 ring-amber-200" },
};

const RISK: Record<RiskLevel, { label: string; className: string }> = {
  low: { label: "Risque faible", className: "text-emerald-700" },
  medium: { label: "Risque moyen", className: "text-amber-700" },
  high: { label: "Risque élevé", className: "text-rose-700" },
};

function formatDate(iso: string) {
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

export default function HistoryPage() {
  const me = useCurrentUser();
  const [role, setRole] = useState<Role>("all");
  const [items, setItems] = useState<Verification[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<Verification[]>(`/verifications?role=${role}&limit=50`)
      .then((list) => !cancelled && setItems(list))
      .catch((err) => setError(errorText(err)));
    return () => {
      cancelled = true;
    };
  }, [role]);

  function changeTab(next: Role) {
    setRole(next);
    setItems(null);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Historique</h1>
        <p className="mt-1 text-sm text-slate-600">Toutes les vérifications qui vous concernent, les plus récentes en premier.</p>
      </div>

      <div className="inline-grid grid-cols-3 gap-1 rounded-lg bg-slate-100 p-1" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={role === tab.value}
            onClick={() => changeTab(tab.value)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition ${
              role === tab.value ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      {items === null ? (
        <p className="text-sm text-slate-500">Chargement…</p>
      ) : items.length === 0 ? (
        <Card className="text-center">
          <p className="text-sm text-slate-600">Aucune vérification pour l&apos;instant.</p>
        </Card>
      ) : (
        <Card className="p-0">
          <ul className="divide-y divide-slate-100">
            {items.map((item) => {
              const sent = item.requester_id === me.id;
              const status = STATUS[item.status];
              const risk = RISK[item.risk.level];
              return (
                <li key={item.id} className="flex flex-wrap items-start justify-between gap-3 p-5">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {sent ? "Vous avez vérifié un appel" : "Un proche a vérifié si c'était vous"}
                    </p>
                    {item.note && <p className="mt-1 truncate text-sm text-slate-600">« {item.note} »</p>}
                    <p className="mt-1 text-xs text-slate-500">
                      {formatDate(item.created_at)} ·{" "}
                      <span className={`font-medium ${risk.className}`}>{risk.label}</span>
                    </p>
                  </div>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${status.className}`}>
                    {status.label}
                  </span>
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </div>
  );
}
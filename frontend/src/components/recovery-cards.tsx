"use client";

import { useState, type FormEvent } from "react";

import { Alert, Button, Card, Field } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { signMessage, type StoredDevice } from "@/lib/device-keys";
import type { Device } from "@/lib/types";

type ApprovalStatus = { device_id: string; approvals: number; required: number; can_confirm: boolean };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Doit être identique à approval_message() dans backend/app/api/devices.py.
function approvalMessage(deviceId: string, approverId: string) {
  return `echoshield:v1:approve-device:${deviceId}:${approverId}`;
}

// ---------------------------------------------------------------------------
// Côté papa : son nouvel appareil attend 24 h, il demande de l'aide.
// ---------------------------------------------------------------------------

export function RequestApprovalCard({ device, onRefresh }: { device: Device; onRefresh: () => void }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(device.id);
      setCopied(true);
    } catch {
      // L'utilisateur peut sélectionner le code à la main.
    }
  }

  return (
    <Card>
      <h2 className="font-semibold">Activer cet appareil plus tôt</h2>
      <p className="mt-1 text-sm text-slate-600">
        Vous avez changé de téléphone ? Deux membres de confiance de vos cercles peuvent valider cet appareil
        depuis leur propre téléphone. Il deviendra actif immédiatement.
      </p>
      <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm text-slate-700">
        <li>Envoyez ce code à deux proches de confiance.</li>
        <li>Chacun le colle dans « Valider le téléphone d&apos;un proche », sur sa page Mon téléphone.</li>
        <li>Revenez ici et cliquez sur « Actualiser ».</li>
      </ol>
      <code className="mt-4 block break-all rounded-lg bg-slate-50 px-3 py-2 font-mono text-sm ring-1 ring-slate-200">
        {device.id}
      </code>
      <div className="mt-3 flex flex-wrap gap-3">
        <Button variant="secondary" onClick={copy}>
          {copied ? "Copié ✓" : "Copier le code"}
        </Button>
        <Button variant="secondary" onClick={onRefresh}>
          Actualiser
        </Button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Côté proche : il valide, avec une signature de SON appareil.
// ---------------------------------------------------------------------------

type Message = { tone: "error" | "success" | "info"; text: string };

export function ApproveDeviceCard({ stored, meId }: { stored: StoredDevice; meId: string }) {
  const [deviceId, setDeviceId] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<Message | null>(null);

  async function approve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);

    const target = deviceId.trim();
    if (!UUID.test(target)) {
      setMessage({ tone: "error", text: "Ce code n'a pas le bon format." });
      return;
    }

    setBusy(true);
    try {
      const signature = await signMessage(stored.privateKey, approvalMessage(target, meId));
      const result = await api<ApprovalStatus>(`/devices/${target}/approvals`, {
        method: "POST",
        body: { approver_device_id: stored.deviceId, signature },
      });
      setDeviceId("");
      setMessage(
        result.can_confirm
          ? {
              tone: "success",
              text: "✅ Validation signée envoyée. Avec les deux validations, le téléphone de votre proche est maintenant actif.",
            }
          : {
              tone: "info",
              text: `Validation signée envoyée (${result.approvals}/${result.required}). Il manque encore ${result.required - result.approvals} validation d'un autre proche.`,
            },
      );
    } catch (err) {
      setMessage({ tone: "error", text: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="font-semibold">Valider le téléphone d&apos;un proche</h2>
      <p className="mt-1 text-sm text-slate-600">
        Un proche a changé de téléphone et vous a envoyé un code ? Ne validez que si vous l&apos;avez joint par
        un autre moyen et êtes sûr que c&apos;est bien lui.
      </p>
      <form onSubmit={approve} className="mt-4 space-y-3">
        <Field
          id="approve_device"
          label="Code de l'appareil"
          autoComplete="off"
          required
          value={deviceId}
          onChange={(e) => setDeviceId(e.target.value)}
        />
        {message && <Alert tone={message.tone}>{message.text}</Alert>}
        <Button type="submit" disabled={busy}>
          {busy ? "Signature…" : "Valider cet appareil"}
        </Button>
      </form>
    </Card>
  );
}
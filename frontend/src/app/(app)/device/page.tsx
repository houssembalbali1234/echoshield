"use client";

import { useEffect, useState, type FormEvent } from "react";

import { useCurrentUser } from "@/components/app-shell";
import { Alert, Button, Card, Field } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import {
  forgetDevice,
  generateDeviceKey,
  loadDevice,
  saveDevice,
  signMessage,
  type StoredDevice,
} from "@/lib/device-keys";
import type { Device, IncomingChallenge } from "@/lib/types";

const POLL_SECONDS = 4;

function formatDate(iso: string) {
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

function formatTime(iso: string) {
  return new Intl.DateTimeFormat("fr-FR", { timeStyle: "short" }).format(new Date(iso));
}

export default function DevicePage() {
  const me = useCurrentUser();

  // undefined = en cours de chargement ; null = aucune clé dans ce navigateur.
  const [stored, setStored] = useState<StoredDevice | null | undefined>(undefined);
  const [devices, setDevices] = useState<Device[]>([]);
  const [challenges, setChallenges] = useState<IncomingChallenge[]>([]);
  const [version, setVersion] = useState(0);
  const [name, setName] = useState("Ce navigateur");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // 1. Au chargement : la clé de ce navigateur, et la liste des appareils côté API.
  useEffect(() => {
    let cancelled = false;
    Promise.all([loadDevice(me.id), api<Device[]>("/devices")])
      .then(([device, list]) => {
        if (cancelled) return;
        setStored(device ?? null);
        setDevices(list);
      })
      .catch((err) => setError(errorText(err)));
    return () => {
      cancelled = true;
    };
  }, [me.id, version]);

  const thisDevice = stored ? devices.find((d) => d.id === stored.deviceId) : undefined;
  const isActive = thisDevice?.status === "active";

  // 2. Si ce navigateur est un appareil actif : on regarde les défis toutes les 4 secondes.
  useEffect(() => {
    if (!isActive) return;
    let cancelled = false;
    const load = () =>
      api<IncomingChallenge[]>("/verifications/incoming")
        .then((list) => !cancelled && setChallenges(list))
        .catch(() => {});
    load();
    const timer = setInterval(load, POLL_SECONDS * 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [isActive, version]);

  function reset() {
    setError(null);
    setSuccess(null);
  }

  async function registerDevice(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    reset();
    if (!window.crypto?.subtle) {
      setError("Ce navigateur ne permet pas de générer des clés (WebCrypto indisponible).");
      return;
    }
    setBusy("register");
    try {
      await forgetDevice(me.id);
      const { privateKey, publicPem } = await generateDeviceKey();
      const device = await api<Device>("/devices", {
        method: "POST",
        body: { name: name.trim(), public_key: publicPem },
      });
      await saveDevice({ userId: me.id, deviceId: device.id, privateKey });
      setSuccess(
        device.can_confirm
          ? "Ce navigateur est enregistré et peut répondre aux vérifications."
          : `Ce navigateur est enregistré. Par sécurité, il pourra confirmer à partir du ${formatDate(device.activates_at)}.`,
      );
      setVersion((v) => v + 1);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function answer(challenge: IncomingChallenge, decision: "confirm" | "deny") {
    if (!stored) return;
    reset();
    setBusy(challenge.id);
    try {
      const message =
        decision === "confirm" ? challenge.message_to_sign_confirm : challenge.message_to_sign_deny;
      const signature = await signMessage(stored.privateKey, message);
      await api(`/verifications/${challenge.id}/respond`, {
        method: "POST",
        body: { device_id: stored.deviceId, decision, signature },
      });
      setSuccess(
        decision === "confirm"
          ? `Réponse signée envoyée : ${challenge.requester_name} sait que c'est bien vous.`
          : `Réponse signée envoyée : ${challenge.requester_name} est prévenu(e) que ce n'est pas vous.`,
      );
      setChallenges((list) => list.filter((c) => c.id !== challenge.id));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function revoke(device: Device) {
    if (!window.confirm(`Révoquer « ${device.name} » ? Il ne pourra plus jamais répondre.`)) return;
    reset();
    try {
      await api(`/devices/${device.id}`, { method: "DELETE" });
      if (device.id === stored?.deviceId) await forgetDevice(me.id);
      setSuccess(`« ${device.name} » est révoqué.`);
      setVersion((v) => v + 1);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Mon téléphone</h1>
        <p className="mt-1 text-sm text-slate-600">
          Quand un proche vérifie un appel à votre nom, c&apos;est ici que vous répondez. Votre réponse est
          signée avec une clé qui ne quitte jamais cet appareil.
        </p>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {success && <Alert tone="success">{success}</Alert>}

      <Card>
        <h2 className="font-semibold">Cet appareil</h2>

        {stored === undefined ? (
          <p className="mt-3 text-sm text-slate-500">Chargement…</p>
        ) : !stored ? (
          <form onSubmit={registerDevice} className="mt-4 space-y-4">
            <p className="text-sm text-slate-600">
              Ce navigateur n&apos;est pas encore enregistré. Il va générer une paire de clés : la clé privée
              reste ici et ne peut pas être lue, seule la clé publique est envoyée à EchoShield.
            </p>
            <Field
              id="device_name"
              label="Nom de l'appareil"
              required
              minLength={2}
              maxLength={80}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <Button type="submit" disabled={busy !== null}>
              {busy === "register" ? "Génération des clés…" : "Enregistrer ce navigateur"}
            </Button>
          </form>
        ) : isActive && thisDevice ? (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-medium">{thisDevice.name}</p>
              <p className="text-sm text-slate-600">Enregistré le {formatDate(thisDevice.created_at)}</p>
            </div>
            {thisDevice.can_confirm ? (
              <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
                Peut confirmer
              </span>
            ) : (
              <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">
                Peut confirmer le {formatDate(thisDevice.activates_at)}
              </span>
            )}
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            <Alert tone="warning">
              La clé de ce navigateur n&apos;est plus valable : l&apos;appareil a été révoqué ou supprimé.
            </Alert>
            <Button onClick={() => registerDevice()} disabled={busy !== null}>
              Enregistrer à nouveau ce navigateur
            </Button>
          </div>
        )}
      </Card>

      {isActive && (
        <Card>
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold">Demandes de vérification</h2>
            <span className="text-xs text-slate-500">Actualisation toutes les {POLL_SECONDS} s</span>
          </div>

          {challenges.length === 0 ? (
            <p className="mt-3 text-sm text-slate-600">Aucune demande en attente.</p>
          ) : (
            <ul className="mt-4 space-y-4">
              {challenges.map((challenge) => (
                <li key={challenge.id} className="rounded-xl border border-indigo-200 bg-indigo-50 p-4">
                  <p className="font-medium text-indigo-950">
                    {challenge.requester_name} vérifie si c&apos;est bien vous qui l&apos;appelez.
                  </p>
                  {challenge.note && <p className="mt-1 text-sm text-indigo-900">« {challenge.note} »</p>}
                                   <p className="mt-1 text-xs text-indigo-800">Expire à {formatTime(challenge.expires_at)}</p>
                  {!thisDevice?.can_confirm && (
                    <p className="mt-3 text-sm text-amber-800">
                      Cet appareil est récent : par sécurité, il pourra répondre à partir du{" "}
                      {thisDevice && formatDate(thisDevice.activates_at)}. Répondez depuis un appareil plus
                      ancien.
                    </p>
                  )}
                  <div className="mt-4 flex flex-wrap gap-3">
                    <Button
                      variant="success"
                      disabled={busy !== null || !thisDevice?.can_confirm}
                      onClick={() => answer(challenge, "confirm")}
                    >
                      Oui, c&apos;est moi
                    </Button>
                    <Button
                      variant="danger"
                        disabled={busy !== null || !thisDevice?.can_confirm}
                      onClick={() => answer(challenge, "deny")}
                    >
                      Non, ce n&apos;est pas moi
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {devices.length > 0 && (
        <Card>
          <h2 className="font-semibold">Tous mes appareils</h2>
          <ul className="mt-4 divide-y divide-slate-100">
            {devices.map((device) => (
              <li key={device.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-medium">
                    {device.name}
                    {device.id === stored?.deviceId && (
                      <span className="font-normal text-slate-500"> (ce navigateur)</span>
                    )}
                  </p>
                  <p className="text-sm text-slate-600">
                    {device.status === "revoked"
                      ? `Révoqué le ${formatDate(device.revoked_at!)}`
                      : `Ajouté le ${formatDate(device.created_at)}`}
                  </p>
                </div>
                {device.status === "active" && (
                  <button
                    onClick={() => revoke(device)}
                    className="text-sm font-medium text-rose-600 hover:text-rose-700"
                  >
                    Révoquer
                  </button>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
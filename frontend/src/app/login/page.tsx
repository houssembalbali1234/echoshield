"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert, Button, Card, Field, Logo } from "@/components/ui";
import { api, ApiError, tokens } from "@/lib/api";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    tokens.clear();

    try {
      if (mode === "register") {
        await api("/auth/register", {
          method: "POST",
          body: { email, full_name: fullName, password },
        });
      }
      const pair = await api<{ access_token: string; refresh_token: string }>("/auth/login", {
        method: "POST",
        body: { email, password },
      });
      tokens.save(pair);
      router.push("/circles");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de joindre le serveur.");
    } finally {
      setLoading(false);
    }
  }

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-12">
      <div className="mb-8 text-center">
        <Logo />
        <p className="mt-3 text-sm text-slate-600">Vérifier la demande, pas la voix.</p>
      </div>

      <Card>
        <div className="mb-6 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1" role="tablist">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              onClick={() => switchMode(m)}
              className={`rounded-md py-2 text-sm font-medium transition ${
                mode === m ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {m === "login" ? "Connexion" : "Créer un compte"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "register" && (
            <Field
              id="full_name"
              label="Nom complet"
              autoComplete="name"
              required
              minLength={2}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          )}
          <Field
            id="email"
            label="E-mail"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Field
            id="password"
            label="Mot de passe"
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={mode === "register" ? 12 : undefined}
            hint={mode === "register" ? "12 caractères minimum." : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && <Alert tone="error">{error}</Alert>}

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Un instant…" : mode === "login" ? "Se connecter" : "Créer mon compte"}
          </Button>
        </form>
      </Card>
    </main>
  );
}
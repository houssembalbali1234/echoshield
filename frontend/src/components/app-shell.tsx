"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { Logo } from "@/components/ui";
import { api, tokens } from "@/lib/api";
import type { User } from "@/lib/types";

const NAV = [
  { href: "/circles", label: "Mes cercles" },
  { href: "/verify", label: "Vérifier un appel" },
  { href: "/device", label: "Mon téléphone" },
  { href: "/history", label: "Historique" },
];

const UserContext = createContext<User | null>(null);

// Donne l'utilisateur connecté à n'importe quelle page du cadre.
export function useCurrentUser(): User {
  const user = useContext(UserContext);
  if (!user) throw new Error("useCurrentUser doit être utilisé dans AppShell");
  return user;
}

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!tokens.access && !tokens.refresh) {
      router.replace("/login");
      return;
    }
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => {
        tokens.clear();
        router.replace("/login");
      });
  }, [router]);

  async function logout() {
    const refreshToken = tokens.refresh;
    if (refreshToken) {
      try {
        await api("/auth/logout", { method: "POST", body: { refresh_token: refreshToken } });
      } catch {
        // Même si l'API ne répond pas, on efface les jetons localement.
      }
    }
    tokens.clear();
    router.replace("/login");
  }

  if (!user) {
    return <div className="grid min-h-screen place-items-center text-sm text-slate-500">Chargement…</div>;
  }

  return (
    <UserContext.Provider value={user}>
      <div className="min-h-screen">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
            <Link href="/circles">
              <Logo />
            </Link>
            <div className="flex items-center gap-3 text-sm">
              <span className="hidden text-slate-600 sm:inline">{user.full_name}</span>
              <button
                onClick={logout}
                className="rounded-lg px-3 py-1.5 font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              >
                Se déconnecter
              </button>
            </div>
          </div>
          <nav className="mx-auto flex max-w-5xl gap-1 overflow-x-auto px-4">
            {NAV.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium ${
                    active
                      ? "border-indigo-600 text-indigo-700"
                      : "border-transparent text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </div>
    </UserContext.Provider>
  );
}
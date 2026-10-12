// Client unique de l'API EchoShield : jetons, renouvellement automatique, erreurs.

const ACCESS_KEY = "echoshield.access_token";
const REFRESH_KEY = "echoshield.refresh_token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type TokenPair = { access_token: string; refresh_token: string };

// ---------------------------------------------------------------------------
// Stockage des jetons
// ---------------------------------------------------------------------------

function read(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export const tokens = {
  get access() {
    return read(ACCESS_KEY);
  },
  get refresh() {
    return read(REFRESH_KEY);
  },
  save(pair: TokenPair) {
    try {
      window.localStorage.setItem(ACCESS_KEY, pair.access_token);
      window.localStorage.setItem(REFRESH_KEY, pair.refresh_token);
    } catch {
      // Stockage indisponible (navigation privée stricte) : la session ne survivra pas au rechargement.
    }
  },
  clear() {
    try {
      window.localStorage.removeItem(ACCESS_KEY);
      window.localStorage.removeItem(REFRESH_KEY);
    } catch {
      // Rien à faire.
    }
  },
};

// ---------------------------------------------------------------------------
// Renouvellement automatique du jeton d'accès
// ---------------------------------------------------------------------------

let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const refreshToken = tokens.refresh;
  if (!refreshToken) return false;

  const response = await fetch("/api/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    tokens.clear();
    return false;
  }
  tokens.save(await response.json());
  return true;
}

// ---------------------------------------------------------------------------
// Messages d'erreur lisibles
// ---------------------------------------------------------------------------

async function errorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: { msg: string }) => d.msg).join(" · ");
    }
  } catch {
    // Pas de JSON dans la réponse.
  }
  return `Erreur ${response.status}`;
}

// ---------------------------------------------------------------------------
// La fonction utilisée par tous les écrans
// ---------------------------------------------------------------------------

type Options = {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
};

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const send = () => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const access = tokens.access;
    if (access) headers.Authorization = `Bearer ${access}`;
    return fetch(`/api${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  };

  let response = await send();

  // Jeton d'accès expiré : on le renouvelle une seule fois, puis on rejoue la requête.
  if (response.status === 401 && tokens.refresh) {
    refreshing ??= refreshTokens().finally(() => {
      refreshing = null;
    });
    if (await refreshing) response = await send();
  }

  if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}


// Transforme n'importe quelle erreur en message affichable.
export function errorText(err: unknown): string {
  return err instanceof ApiError ? err.message : "Impossible de joindre le serveur.";
}
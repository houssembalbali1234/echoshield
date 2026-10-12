// Le navigateur comme « téléphone » EchoShield : clés ECDSA P-256 avec WebCrypto.
// La clé privée est générée NON EXPORTABLE et rangée dans IndexedDB :
// le navigateur peut signer avec, mais personne ne peut la lire.

const DB_NAME = "echoshield";
const STORE = "device-keys";

export type StoredDevice = {
  userId: string;
  deviceId: string;
  privateKey: CryptoKey;
};

// ---------------------------------------------------------------------------
// Stockage dans IndexedDB (une base de données intégrée au navigateur)
// ---------------------------------------------------------------------------

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "userId" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function run<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const request = action(db.transaction(STORE, mode).objectStore(STORE));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export function loadDevice(userId: string): Promise<StoredDevice | undefined> {
  return run("readonly", (store) => store.get(userId));
}

export function saveDevice(device: StoredDevice): Promise<IDBValidKey> {
  return run("readwrite", (store) => store.put(device));
}

export function forgetDevice(userId: string): Promise<undefined> {
  return run("readwrite", (store) => store.delete(userId));
}

// ---------------------------------------------------------------------------
// Génération de la paire de clés
// ---------------------------------------------------------------------------

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((byte) => (binary += String.fromCharCode(byte)));
  return btoa(binary);
}

function toPem(spki: ArrayBuffer): string {
  const lines = toBase64(new Uint8Array(spki)).match(/.{1,64}/g)!.join("\n");
  return `-----BEGIN PUBLIC KEY-----\n${lines}\n-----END PUBLIC KEY-----\n`;
}

export async function generateDeviceKey(): Promise<{ privateKey: CryptoKey; publicPem: string }> {
  const pair = await crypto.subtle.generateKey(
    { name: "ECDSA", namedCurve: "P-256" },
    false, // clé privée NON exportable
    ["sign", "verify"],
  );
  // La clé publique, elle, est toujours exportable : c'est elle qu'on envoie à l'API.
  const spki = await crypto.subtle.exportKey("spki", pair.publicKey);
  return { privateKey: pair.privateKey, publicPem: toPem(spki) };
}

// ---------------------------------------------------------------------------
// Signature
// ---------------------------------------------------------------------------

// WebCrypto renvoie la signature « brute » (r et s collés, 32 octets chacun).
// Le backend attend le format standard DER : on convertit.
function derInteger(bytes: Uint8Array): number[] {
  let start = 0;
  while (start < bytes.length - 1 && bytes[start] === 0) start++;
  const value = Array.from(bytes.slice(start));
  if (value[0] & 0x80) value.unshift(0); // un entier DER positif ne commence pas par un bit à 1
  return [0x02, value.length, ...value];
}

function rawToDer(raw: Uint8Array): Uint8Array {
  const r = derInteger(raw.slice(0, 32));
  const s = derInteger(raw.slice(32, 64));
  return Uint8Array.from([0x30, r.length + s.length, ...r, ...s]);
}

export async function signMessage(privateKey: CryptoKey, message: string): Promise<string> {
  const raw = await crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    privateKey,
    new TextEncoder().encode(message),
  );
  return toBase64(rawToDer(new Uint8Array(raw)));
}
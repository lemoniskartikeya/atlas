// Client-side encryption for Atlas backups. The passphrase never leaves the
// browser: AES-GCM with a PBKDF2-derived key. Web Crypto is available in secure
// contexts, which includes http://localhost and the Tauri shell.

const ITERATIONS = 200_000;

interface Envelope {
  atlas_encrypted: true;
  v: 1;
  kdf: "PBKDF2-SHA256";
  iterations: number;
  salt: string;
  iv: string;
  ciphertext: string;
}

function toB64(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}

function fromB64(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function deriveKey(passphrase: string, salt: Uint8Array, usage: KeyUsage): Promise<CryptoKey> {
  const material = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(passphrase) as BufferSource,
    "PBKDF2",
    false,
    ["deriveKey"],
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt: salt as BufferSource, iterations: ITERATIONS, hash: "SHA-256" },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    [usage],
  );
}

export function isEncryptedBackup(obj: unknown): obj is Envelope {
  return !!obj && typeof obj === "object" && (obj as Envelope).atlas_encrypted === true;
}

export async function encryptBackup(payload: unknown, passphrase: string): Promise<string> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(passphrase, salt, "encrypt");
  const data = new TextEncoder().encode(JSON.stringify(payload));
  const cipher = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv: iv as BufferSource }, key, data as BufferSource),
  );
  const envelope: Envelope = {
    atlas_encrypted: true,
    v: 1,
    kdf: "PBKDF2-SHA256",
    iterations: ITERATIONS,
    salt: toB64(salt),
    iv: toB64(iv),
    ciphertext: toB64(cipher),
  };
  return JSON.stringify(envelope);
}

export async function decryptBackup(envelope: Envelope, passphrase: string): Promise<unknown> {
  const key = await deriveKey(passphrase, fromB64(envelope.salt), "decrypt");
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: fromB64(envelope.iv) as BufferSource },
    key,
    fromB64(envelope.ciphertext) as BufferSource,
  );
  return JSON.parse(new TextDecoder().decode(plain));
}

export function downloadText(filename: string, text: string): void {
  const blob = new Blob([text], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

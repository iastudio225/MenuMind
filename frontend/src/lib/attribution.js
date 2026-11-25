/**
 * Public link attribution (Lot C).
 *
 * The public experience can be reached from WhatsApp groups (`src=wa`), printed
 * QR codes (`src=qr`), Instagram bios (`src=ig`), etc. The source is persisted
 * on the cart and copied to the order so the dashboard can compute conversion.
 *
 * Telemetry must never break the customer experience: every helper swallows
 * storage/network errors and returns a safe default.
 */
import axios from "axios";

export const SOURCES = ["wa", "qr", "ig", "fb", "web", "direct", "other"];
export const DEFAULT_SOURCE = "direct";
const SOURCE_MAX_LENGTH = 16;
const SESSION_KEY = "mm_session_id";
const inFlight = new Set();

export function normalizeSource(raw) {
  if (raw === null || raw === undefined) return DEFAULT_SOURCE;
  const value = String(raw).trim().toLowerCase().slice(0, SOURCE_MAX_LENGTH);
  if (!value) return DEFAULT_SOURCE;
  return SOURCES.includes(value) ? value : "other";
}

export function readSource(search) {
  const query = search === undefined
    ? (typeof window !== "undefined" ? window.location.search : "")
    : search;
  if (typeof query !== "string") return DEFAULT_SOURCE;
  try {
    return normalizeSource(new URLSearchParams(query).get("src"));
  } catch {
    return DEFAULT_SOURCE;
  }
}

function createSessionId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID().replace(/-/g, "");
  }
  return `mm${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

export function getSessionId(storage) {
  const store = storage || (typeof window !== "undefined" ? window.sessionStorage : null);
  if (!store) return "";
  try {
    const existing = store.getItem(SESSION_KEY);
    if (existing) return existing;
    const created = createSessionId();
    store.setItem(SESSION_KEY, created);
    return created;
  } catch {
    return "";
  }
}

/**
 * Record at most one visit per browser session and restaurant.
 * Returns the backend payload, or null when skipped/failed.
 */
export async function trackVisit(publicId, { search, storage, sessionId, post } = {}) {
  if (!publicId) return null;
  const store = storage || (typeof window !== "undefined" ? window.sessionStorage : null);
  const key = `mm_visit_sent:${publicId}`;
  try {
    if (store && store.getItem(key)) return null;
  } catch {
    // private mode / storage disabled: continue, the backend dedupes anyway
  }
  const id = sessionId || getSessionId(store);
  if (!id) return null;
  if (inFlight.has(`${publicId}:${id}`)) return null;

  const payload = {
    public_id: publicId,
    kind: "visit",
    source: readSource(search),
    session_id: id,
  };
  const send = post || ((body) => axios.post(
    `${process.env.REACT_APP_BACKEND_URL}/api/public/events`, body));

  inFlight.add(`${publicId}:${id}`);
  try {
    const response = await send(payload);
    try {
      if (store) store.setItem(key, "1");
    } catch {
      // ignore storage quota/privacy errors
    }
    return response?.data ?? response;
  } catch {
    return null;
  } finally {
    inFlight.delete(`${publicId}:${id}`);
  }
}

import { useEffect, useRef, useState } from 'react';
import type { AppState, ControlAction, ControlResponse } from './types';

export async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { headers: { Accept: 'application/json' }, signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** POST /api/control/{action}. Always resolves with the backend's {ok, message} (or a transport error). */
export async function postControl(action: ControlAction, confirm: boolean): Promise<ControlResponse> {
  let res: Response;
  try {
    res = await fetch(`/api/control/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(confirm ? { confirm: true } : {}),
    });
  } catch {
    return { ok: false, message: 'Backend unreachable — the command was not delivered.' };
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>;
    if (typeof b.ok === 'boolean') {
      const msg = typeof b.message === 'string' && b.message !== '' ? b.message : b.ok ? 'Done.' : 'Command rejected.';
      return { ok: b.ok, message: msg };
    }
    if (typeof b.detail === 'string') return { ok: false, message: b.detail };
  }
  return { ok: false, message: `Unexpected response from backend (HTTP ${res.status}).` };
}

export interface Polled<T> {
  data: T | null;
  /** Error of the most recent request, null if it succeeded. */
  error: string | null;
  /** True once at least one request has completed (successfully or not). */
  settled: boolean;
}

/**
 * Polls a JSON endpoint while the calling component is mounted. Sections are only
 * mounted while visible, so only the visible section's endpoints are polled.
 */
export function usePoll<T>(url: string, intervalMs = 5000, validate?: (v: unknown) => boolean): Polled<T> {
  const [st, setSt] = useState<Polled<T>>({ data: null, error: null, settled: false });
  const validateRef = useRef(validate);
  validateRef.current = validate;

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;
    const ctrl = new AbortController();
    const tick = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const data = await fetchJson<T>(url, ctrl.signal);
        if (cancelled) return;
        if (validateRef.current && !validateRef.current(data)) throw new Error('Unexpected response shape');
        setSt({ data, error: null, settled: true });
      } catch (e) {
        if (cancelled) return;
        setSt((prev) => ({ data: prev.data, error: e instanceof Error ? e.message : 'Request failed', settled: true }));
      } finally {
        inFlight = false;
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      ctrl.abort();
    };
  }, [url, intervalMs]);

  return st;
}

/** Poll an endpoint that must return a JSON array. */
export function usePollList<T>(url: string, intervalMs = 5000): Polled<T[]> {
  return usePoll<T[]>(url, intervalMs, Array.isArray);
}

export interface LiveState {
  state: AppState | null;
  wsConnected: boolean;
  /** True when the socket is down AND the HTTP fallback is failing too. */
  unreachable: boolean;
  /** Local time (ms) at which the last state snapshot was received. */
  lastUpdate: number | null;
  /** Ask for an immediate refresh (used right after a control command). */
  refresh: () => void;
}

function isState(v: unknown): v is AppState {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/**
 * Live experiment state: WebSocket push, with automatic reconnect and an HTTP
 * polling fallback (/api/state every 3 s) for as long as the socket is down.
 */
export function useLiveState(): LiveState {
  const [state, setState] = useState<AppState | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [httpFailed, setHttpFailed] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let stopped = false;
    let sock: WebSocket | null = null;
    let timer: number | undefined;
    let attempt = 0;

    const schedule = () => {
      if (stopped) return;
      attempt += 1;
      timer = window.setTimeout(connect, Math.min(1000 * 2 ** (attempt - 1), 10000));
    };

    function connect() {
      if (stopped) return;
      const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
      let s: WebSocket;
      try {
        s = new WebSocket(url);
      } catch {
        schedule();
        return;
      }
      sock = s;
      s.onopen = () => {
        attempt = 0;
        setWsConnected(true);
        setHttpFailed(false);
      };
      s.onmessage = (ev) => {
        try {
          const msg: unknown = JSON.parse(String(ev.data));
          if (isState(msg)) {
            const m = msg as { type?: unknown; data?: unknown };
            if (m.type === 'state' && isState(m.data)) {
              setState(m.data);
              setLastUpdate(Date.now());
            }
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      s.onerror = () => {
        try {
          s.close();
        } catch {
          /* already closed */
        }
      };
      s.onclose = () => {
        if (stopped || sock !== s) return;
        setWsConnected(false);
        schedule();
      };
    }

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      if (sock) sock.close();
    };
  }, []);

  // HTTP fallback while the socket is down.
  useEffect(() => {
    if (wsConnected) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const s = await fetchJson<unknown>('/api/state');
        if (cancelled) return;
        if (!isState(s)) throw new Error('bad state');
        setState(s);
        setLastUpdate(Date.now());
        setHttpFailed(false);
      } catch {
        if (!cancelled) setHttpFailed(true);
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 3000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [wsConnected]);

  // On-demand refresh (after a control command) so the UI does not wait for the next push.
  useEffect(() => {
    if (nonce === 0) return;
    let cancelled = false;
    fetchJson<unknown>('/api/state')
      .then((s) => {
        if (!cancelled && isState(s)) {
          setState(s);
          setLastUpdate(Date.now());
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [nonce]);

  return {
    state,
    wsConnected,
    unreachable: !wsConnected && httpFailed,
    lastUpdate,
    refresh: () => setNonce((n) => n + 1),
  };
}

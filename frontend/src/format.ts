// Formatting helpers. Rule: a missing / null / non-finite value is always "—".
// Nothing in here ever substitutes a default number.

export const DASH = '—';

export function isNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

const moneyCache = new Map<string, Intl.NumberFormat>();
function moneyFmt(currency: string, signed: boolean): Intl.NumberFormat {
  const key = `${currency}|${signed}`;
  let f = moneyCache.get(key);
  if (!f) {
    try {
      f = new Intl.NumberFormat('en-IE', {
        style: 'currency',
        currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
        signDisplay: signed ? 'exceptZero' : 'auto',
      });
    } catch {
      f = new Intl.NumberFormat('en-IE', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
        signDisplay: signed ? 'exceptZero' : 'auto',
      });
    }
    moneyCache.set(key, f);
  }
  return f;
}

/** Money with 2 decimals (EUR unless another ISO currency is given). */
export function money(v: unknown, currency?: string | null): string {
  return isNum(v) ? moneyFmt(currency || 'EUR', false).format(v) : DASH;
}

/** Money with an explicit +/- sign, for P&L values. */
export function signedMoney(v: unknown, currency?: string | null): string {
  return isNum(v) ? moneyFmt(currency || 'EUR', true).format(v) : DASH;
}

const pctFmt = new Intl.NumberFormat('en-IE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pctSigned = new Intl.NumberFormat('en-IE', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'exceptZero',
});

/** A value that is already expressed in percent (e.g. 1.25 -> "1.25%"). */
export function pct(v: unknown, signed = false): string {
  return isNum(v) ? `${(signed ? pctSigned : pctFmt).format(v)}%` : DASH;
}

/** A 0..1 fraction shown as a percentage (e.g. 0.5 -> "50.00%"). */
export function fractionPct(v: unknown): string {
  return isNum(v) ? `${pctFmt.format(v * 100)}%` : DASH;
}

export function num(v: unknown, digits = 2, signed = false): string {
  if (!isNum(v)) return DASH;
  return new Intl.NumberFormat('en-IE', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: signed ? 'exceptZero' : 'auto',
  }).format(v);
}

export function int(v: unknown): string {
  return isNum(v) ? new Intl.NumberFormat('en-IE', { maximumFractionDigits: 0 }).format(v) : DASH;
}

/** Quantity: up to 8 decimals, trailing zeros trimmed. */
export function qty(v: unknown): string {
  return isNum(v) ? new Intl.NumberFormat('en-IE', { maximumFractionDigits: 8 }).format(v) : DASH;
}

/** Instrument price: precision adapts to magnitude (forex / small-cap crypto need more decimals). */
export function price(v: unknown): string {
  if (!isNum(v)) return DASH;
  const a = Math.abs(v);
  const max = a >= 1000 ? 2 : a >= 100 ? 3 : a >= 1 ? 5 : 8;
  return new Intl.NumberFormat('en-IE', { minimumFractionDigits: 2, maximumFractionDigits: max }).format(v);
}

const compactFmt = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 });
export function compact(v: unknown): string {
  return isNum(v) ? compactFmt.format(v) : DASH;
}

function parseTs(ts: unknown): Date | null {
  if (typeof ts !== 'string' || ts === '') return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function tsMillis(ts: unknown): number | null {
  const d = parseTs(ts);
  return d ? d.getTime() : null;
}

/** Timestamp in the browser's local time zone. */
export function dateTime(ts: unknown): string {
  const d = parseTs(ts);
  if (!d) return DASH;
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/** Calendar date (for report / filing dates that carry no time of day). */
export function dateOnly(ts: unknown): string {
  if (typeof ts !== 'string' || ts === '') return DASH;
  // Plain YYYY-MM-DD strings are calendar dates: do not shift them across time zones.
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ts);
  const d = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : parseTs(ts);
  if (!d || Number.isNaN(d.getTime())) return DASH;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: '2-digit' });
}

export function clockTime(ms: number | null): string {
  if (ms === null) return DASH;
  return new Date(ms).toLocaleTimeString(undefined, { hour12: false });
}

/** Seconds -> "1d 02h 03m 04s". */
export function dhms(seconds: unknown): string {
  if (!isNum(seconds)) return DASH;
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d}d ${p(h)}h ${p(m)}m ${p(sec)}s`;
}

/** Minutes -> "2d 3h", "3h 05m", "12.5m". */
export function minutes(v: unknown): string {
  if (!isNum(v)) return DASH;
  if (v < 60) return `${num(v, v < 10 ? 1 : 0)}m`;
  const total = Math.round(v);
  const d = Math.floor(total / 1440);
  const h = Math.floor((total % 1440) / 60);
  const m = total % 60;
  if (d > 0) return `${d}d ${h}h`;
  return `${h}h ${String(m).padStart(2, '0')}m`;
}

export function text(v: unknown): string {
  if (v === null || v === undefined || v === '') return DASH;
  return String(v);
}

/** snake_case / UPPER_SNAKE -> readable label. */
export function label(v: unknown): string {
  if (typeof v !== 'string' || v === '') return DASH;
  return v.replace(/_/g, ' ');
}

/** Tailwind colour class for a P&L-like value. */
export function pnlClass(v: unknown): string {
  if (!isNum(v) || v === 0) return 'text-ink';
  return v > 0 ? 'text-pos' : 'text-neg';
}

/** Only http(s) links from the backend are ever rendered as anchors. */
export function safeUrl(v: unknown): string | null {
  if (typeof v !== 'string') return null;
  return /^https?:\/\//i.test(v.trim()) ? v.trim() : null;
}

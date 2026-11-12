import type { ReactNode } from 'react';
import type { Polled } from './api';
import { DASH, isNum } from './format';

export type Tone = 'neutral' | 'pos' | 'neg' | 'warn' | 'accent' | 'dim';

const pillTone: Record<Tone, string> = {
  neutral: 'border-line bg-raised text-mute',
  pos: 'border-pos/40 bg-pos/10 text-pos',
  neg: 'border-neg/40 bg-neg/10 text-neg',
  warn: 'border-warn/40 bg-warn/10 text-warn',
  accent: 'border-accent/40 bg-accent/10 text-accent',
  dim: 'border-line bg-transparent text-dim',
};

export function Pill({ tone = 'neutral', children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-px text-[10.5px] font-semibold uppercase tracking-wide whitespace-nowrap ${pillTone[tone]}`}
    >
      {children}
    </span>
  );
}

/** Yes / no / unknown flag. Unknown (null) renders as "—". */
export function Flag({
  value,
  yes,
  no,
  yesTone = 'pos',
  noTone = 'dim',
}: {
  value: boolean | null | undefined;
  yes: string;
  no: string;
  yesTone?: Tone;
  noTone?: Tone;
}) {
  if (typeof value !== 'boolean') return <span className="text-dim">{DASH}</span>;
  return <Pill tone={value ? yesTone : noTone}>{value ? yes : no}</Pill>;
}

export function Panel({
  title,
  right,
  children,
  className = '',
  flush = false,
}: {
  title: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section className={`min-w-0 rounded-md border border-line bg-panel ${className}`}>
      <header className="flex min-h-9 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line px-3 py-1.5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-mute">{title}</h2>
        {right ? <div className="flex min-w-0 flex-wrap items-center gap-2 text-[11px] text-mute">{right}</div> : null}
      </header>
      <div className={flush ? '' : 'p-3'}>{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  className = 'text-ink',
  sub,
}: {
  label: string;
  value: string;
  className?: string;
  sub?: ReactNode;
}) {
  return (
    <div className="min-w-0 rounded-md border border-line bg-panel px-3 py-2">
      <div className="truncate text-[10.5px] font-medium uppercase tracking-wider text-mute">{label}</div>
      <div className={`num mt-0.5 truncate text-[17px] font-semibold leading-6 ${value === DASH ? 'text-dim' : className}`} title={value}>
        {value}
      </div>
      {sub ? <div className="mt-0.5 truncate text-[11px] text-mute">{sub}</div> : null}
    </div>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-7">{children}</div>;
}

export function ProgressBar({ value, tone = 'accent', label }: { value: number | null; tone?: 'accent' | 'pos' | 'warn'; label: string }) {
  const v = isNum(value) ? Math.min(100, Math.max(0, value)) : null;
  const color = tone === 'pos' ? 'bg-pos' : tone === 'warn' ? 'bg-warn' : 'bg-accent';
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={v ?? undefined}
      className="h-1.5 w-full overflow-hidden rounded-full bg-raised"
    >
      {v !== null ? <div className={`h-full rounded-full ${color} transition-[width] duration-500`} style={{ width: `${v}%` }} /> : null}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-3 py-6 text-center text-[12.5px] text-mute">{children}</p>;
}

/** Small "last refresh failed" marker shown next to data that is being kept from an earlier poll. */
export function StaleNote({ polled }: { polled: Polled<unknown> }) {
  if (!polled.error || polled.data === null) return null;
  return <Pill tone="warn" title={`Last refresh failed: ${polled.error}`}>refresh failed</Pill>;
}

/**
 * Renders the loading / error states of a polled resource, and hands the data to
 * `children` only when there is real data from the backend.
 */
export function Loadable<T>({
  polled,
  what,
  children,
}: {
  polled: Polled<T>;
  what: string;
  children: (data: T) => ReactNode;
}) {
  if (polled.data === null) {
    if (!polled.settled) return <Empty>Loading {what}…</Empty>;
    return <Empty>Could not load {what} from the backend ({polled.error ?? 'no response'}).</Empty>;
  }
  return <>{children(polled.data)}</>;
}

export interface Col<T> {
  key: string;
  header: ReactNode;
  align?: 'left' | 'right' | 'center';
  cell: (row: T) => ReactNode;
  /** Extra classes for body cells. */
  className?: string;
  /** Optional column group label (rendered as a spanning header row). */
  group?: string;
}

const alignCls = { left: 'text-left', right: 'text-right', center: 'text-center' } as const;

/** Dense table. Scrolls horizontally (and optionally vertically) inside its own container. */
export function DataTable<T>({
  cols,
  rows,
  rowKey,
  empty,
  maxHeight,
  rowClass,
}: {
  cols: Col<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  empty: string;
  maxHeight?: number;
  rowClass?: (row: T) => string;
}) {
  if (rows.length === 0) return <Empty>{empty}</Empty>;
  const hasGroups = cols.some((c) => c.group);
  const groups: { label: string; span: number }[] = [];
  if (hasGroups) {
    for (const c of cols) {
      const g = c.group ?? '';
      const last = groups[groups.length - 1];
      if (last && last.label === g) last.span += 1;
      else groups.push({ label: g, span: 1 });
    }
  }
  return (
    <div className="w-full overflow-auto" style={maxHeight ? { maxHeight } : undefined} tabIndex={0} role="region" aria-label="Scrollable table">
      <table className="w-full border-collapse text-[12px]">
        <thead className="sticky top-0 z-10 bg-raised">
          {hasGroups ? (
            <tr>
              {groups.map((g, i) => (
                <th
                  key={`${g.label}-${i}`}
                  colSpan={g.span}
                  className={`px-2.5 pt-1.5 text-center text-[10px] font-semibold uppercase tracking-[0.14em] text-accent ${g.label ? 'border-l border-line' : ''}`}
                >
                  {g.label}
                </th>
              ))}
            </tr>
          ) : null}
          <tr>
            {cols.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={`border-b border-line px-2.5 py-1.5 text-[10.5px] font-semibold uppercase tracking-wider whitespace-nowrap text-mute ${alignCls[c.align ?? 'left']}`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey(r, i)} className={`border-b border-line/60 last:border-b-0 hover:bg-raised/60 ${rowClass ? rowClass(r) : ''}`}>
              {cols.map((c) => (
                <td key={c.key} className={`px-2.5 py-1.5 align-middle whitespace-nowrap ${alignCls[c.align ?? 'left']} ${c.className ?? ''}`}>
                  {c.cell(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Numeric cell content: monospace, dimmed when the value is unavailable. */
export function Num({ children, className = '' }: { children: string; className?: string }) {
  return <span className={`num ${children === DASH ? 'text-dim' : className}`}>{children}</span>;
}

export function SideTag({ side }: { side: string | null | undefined }) {
  if (!side) return <span className="text-dim">{DASH}</span>;
  const s = side.toLowerCase();
  const tone: Tone = s === 'long' || s === 'buy' ? 'pos' : s === 'short' || s === 'sell' ? 'neg' : 'neutral';
  return <Pill tone={tone}>{side}</Pill>;
}

export function ExtLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent">
      {children}
    </a>
  );
}

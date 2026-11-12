import type { LiveState } from './api';
import { clockTime, dhms, isNum, label } from './format';
import { Pill, ProgressBar, type Tone } from './ui';

export const STATUS_TONE: Record<string, Tone> = {
  idle: 'neutral',
  running: 'pos',
  paused: 'warn',
  stopped: 'neutral',
  halted: 'neg',
  completed: 'accent',
};

export interface TabDef {
  id: string;
  label: string;
}

export function Header({
  live,
  tabs,
  active,
  onSelect,
}: {
  live: LiveState;
  tabs: TabDef[];
  active: string;
  onSelect: (id: string) => void;
}) {
  const exp = live.state?.experiment ?? null;
  const status = typeof exp?.status === 'string' ? exp.status : null;
  const elapsed = exp?.elapsed_seconds ?? null;
  const remaining = exp?.remaining_seconds ?? null;
  const totalSeconds = isNum(exp?.duration_days)
    ? exp.duration_days * 86400
    : isNum(elapsed) && isNum(remaining)
      ? elapsed + remaining
      : null;
  const progress = isNum(elapsed) && isNum(totalSeconds) && totalSeconds > 0 ? (elapsed / totalSeconds) * 100 : null;
  const days = isNum(exp?.duration_days) ? `${exp.duration_days}-day clock` : 'Experiment clock';

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1800px] flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2 sm:px-4">
        <div className="flex min-w-0 items-center gap-2">
          <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
            <rect width="32" height="32" rx="6" fill="#131b27" />
            <path d="M5 21l6-7 5 4 6-9 5 5" fill="none" stroke="#4cc2ff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <h1 className="truncate text-[15px] font-semibold tracking-tight text-ink">Quantum Edge AI</h1>
        </div>

        <span
          data-testid="paper-badge"
          className="inline-flex items-center gap-1.5 rounded border border-warn/60 bg-warn/15 px-2 py-1 text-[11px] font-bold uppercase tracking-wider whitespace-nowrap text-warn"
        >
          <span aria-hidden="true">●</span> Paper trading — no real money
        </span>

        <div className="flex items-center gap-2" data-testid="experiment-status">
          <span className="text-[10.5px] font-medium uppercase tracking-wider text-mute">Experiment</span>
          {status ? <Pill tone={STATUS_TONE[status] ?? 'neutral'}>{label(status)}</Pill> : <span className="text-dim">—</span>}
        </div>

        <div className="order-last w-full min-w-0 md:order-none md:w-auto md:flex-1" data-testid="clock" title={days}>
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 text-[11px]">
            <span className="text-mute">
              <span className="hidden uppercase tracking-wider sm:inline">{days}</span>
              <span className="mx-1.5 hidden text-dim sm:inline">·</span>
              elapsed <span className="num text-ink">{dhms(elapsed)}</span>
            </span>
            <span className="text-mute">
              remaining <span className="num text-ink">{dhms(remaining)}</span>
            </span>
          </div>
          <div className="mt-1">
            <ProgressBar value={progress} label="Experiment time elapsed" tone={status === 'paused' ? 'warn' : 'accent'} />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-1.5 text-[11px] whitespace-nowrap md:ml-0" data-testid="ws-indicator" title={`Last state update: ${clockTime(live.lastUpdate)}`}>
          <span className={`inline-block h-2 w-2 rounded-full ${live.wsConnected ? 'bg-pos pulse-dot' : live.unreachable ? 'bg-neg' : 'bg-warn'}`} aria-hidden="true" />
          <span className={live.wsConnected ? 'text-pos' : live.unreachable ? 'text-neg' : 'text-warn'}>
            {live.wsConnected ? 'Live' : live.unreachable ? 'Offline' : 'Polling'}
          </span>
          <span className="hidden text-dim sm:inline">{live.wsConnected ? 'WebSocket' : live.unreachable ? 'no connection' : 'socket down'}</span>
        </div>
      </div>

      <nav aria-label="Sections" className="mx-auto max-w-[1800px] overflow-x-auto px-1 sm:px-2">
        <ul className="flex min-w-max gap-0.5">
          {tabs.map((t) => {
            const on = t.id === active;
            return (
              <li key={t.id}>
                <button
                  type="button"
                  data-tab={t.id}
                  aria-current={on ? 'page' : undefined}
                  onClick={(e) => {
                    onSelect(t.id);
                    e.currentTarget.scrollIntoView({ block: 'nearest', inline: 'center' });
                  }}
                  className={`cursor-pointer border-b-2 px-3 py-2 text-[12px] font-medium whitespace-nowrap transition-colors ${
                    on ? 'border-accent text-ink' : 'border-transparent text-mute hover:text-ink'
                  }`}
                >
                  {t.label}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
    </header>
  );
}

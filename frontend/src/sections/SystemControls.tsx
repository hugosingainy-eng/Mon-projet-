import { useEffect, useRef, useState } from 'react';
import { type LiveState, postControl, usePoll } from '../api';
import { clockTime, dateTime, int, label, text } from '../format';
import { STATUS_TONE } from '../Header';
import type { AppState, ControlAction, ControlResponse, Health } from '../types';
import { Panel, Pill } from '../ui';

type Style = 'primary' | 'neutral' | 'danger';

interface ActionDef {
  id: ControlAction;
  label: string;
  description: string;
  style: Style;
  /** Returns null when the action is available, otherwise the reason it is disabled. */
  blocked: (s: AppState | null) => string | null;
  confirm?: { title: string; body: string; cta: string };
}

const status = (s: AppState | null): string | null => (typeof s?.experiment?.status === 'string' ? s.experiment.status : null);
const needState = (s: AppState | null): string | null => (s === null ? 'Waiting for backend state.' : null);

const ACTIONS: ActionDef[] = [
  {
    id: 'start',
    label: 'Start',
    description: 'Begin the paper-trading experiment.',
    style: 'primary',
    blocked: (s) => {
      const st = status(s);
      return needState(s) ?? (st === 'running' ? 'Already running.' : st === 'paused' ? 'Paused — use Resume.' : null);
    },
  },
  {
    id: 'pause',
    label: 'Pause',
    description: 'Suspend trading; the clock and positions are kept.',
    style: 'neutral',
    blocked: (s) => needState(s) ?? (status(s) === 'running' ? null : 'Only available while running.'),
  },
  {
    id: 'resume',
    label: 'Resume',
    description: 'Continue a paused experiment.',
    style: 'neutral',
    blocked: (s) => needState(s) ?? (status(s) === 'paused' ? null : 'Only available while paused.'),
  },
  {
    id: 'stop',
    label: 'Stop',
    description: 'End the experiment in an orderly way.',
    style: 'neutral',
    blocked: (s) => {
      const st = status(s);
      return needState(s) ?? (st === 'running' || st === 'paused' ? null : 'Nothing is running.');
    },
  },
  {
    id: 'emergency_stop',
    label: 'Emergency stop',
    description: 'Halt everything immediately.',
    style: 'danger',
    blocked: () => null,
    confirm: {
      title: 'Emergency stop?',
      body: 'This immediately halts the experiment and all simulated trading. The experiment will be marked as halted.',
      cta: 'Yes, emergency stop',
    },
  },
  {
    id: 'run_experiments',
    label: 'Run 10,000 experiments',
    description: 'Launch the strategy-lab backtest batch.',
    style: 'primary',
    blocked: (s) => needState(s) ?? (s?.lab?.running === true ? 'A batch is already running.' : null),
  },
  {
    id: 'reset',
    label: 'Reset paper portfolio',
    description: 'Wipe the simulated portfolio back to its initial capital.',
    style: 'danger',
    blocked: (s) => needState(s),
    confirm: {
      title: 'Reset the paper portfolio?',
      body: 'This erases the simulated portfolio, its positions and its trade history, and restores the initial capital. This cannot be undone.',
      cta: 'Yes, reset portfolio',
    },
  },
];

const styleCls: Record<Style, string> = {
  primary: 'border-accent/60 bg-accent/15 text-accent hover:bg-accent/25',
  neutral: 'border-line bg-raised text-ink hover:bg-line',
  danger: 'border-neg/60 bg-neg/15 text-neg hover:bg-neg/25',
};

function ConfirmDialog({ def, busy, onCancel, onConfirm }: { def: ActionDef; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel]);
  const c = def.confirm!;
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4" onMouseDown={(e) => e.target === e.currentTarget && onCancel()}>
      <div role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-body" data-testid="confirm-dialog" className="w-full max-w-md rounded-md border border-neg/50 bg-panel p-4 shadow-2xl shadow-black">
        <h2 id="confirm-title" className="text-[15px] font-semibold text-ink">
          {c.title}
        </h2>
        <p id="confirm-body" className="mt-2 text-[12.5px] text-mute">
          {c.body}
        </p>
        <p className="mt-2 text-[11.5px] text-dim">Paper trading only — no real money is involved.</p>
        <div className="mt-4 flex flex-wrap justify-end gap-2">
          <button ref={cancelRef} type="button" onClick={onCancel} className="cursor-pointer rounded border border-line bg-raised px-3 py-1.5 text-[12px] font-medium text-ink hover:bg-line">
            Cancel
          </button>
          <button
            type="button"
            data-testid="confirm-yes"
            disabled={busy}
            onClick={onConfirm}
            className="cursor-pointer rounded border border-neg/60 bg-neg/20 px-3 py-1.5 text-[12px] font-semibold text-neg hover:bg-neg/30 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? 'Sending…' : c.cta}
          </button>
        </div>
      </div>
    </div>
  );
}

export function SystemControls({ live, notify }: { live: LiveState; notify: (title: string, res: ControlResponse) => void }) {
  const health = usePoll<Health>('/api/health', 5000, (v) => typeof v === 'object' && v !== null && !Array.isArray(v));
  const [busy, setBusy] = useState<ControlAction | null>(null);
  const [pending, setPending] = useState<ActionDef | null>(null);
  const s = live.state;
  const exp = s?.experiment ?? null;
  const st = status(s);

  const run = async (def: ActionDef, confirmed: boolean) => {
    setBusy(def.id);
    const res = await postControl(def.id, confirmed);
    setBusy(null);
    setPending(null);
    notify(def.label, res);
    live.refresh();
  };

  const click = (def: ActionDef) => {
    if (def.confirm) setPending(def);
    else void run(def, false);
  };

  const row = (k: string, v: string, mono = true) => (
    <div className="flex justify-between gap-4 border-b border-line/60 py-1.5 last:border-b-0">
      <dt className="text-mute">{k}</dt>
      <dd className={`min-w-0 break-words text-right text-ink ${mono ? 'num' : ''}`}>{v}</dd>
    </div>
  );

  return (
    <>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[2fr_1fr]">
        <Panel title="System controls" right={st ? <Pill tone={STATUS_TONE[st] ?? 'neutral'}>{label(st)}</Pill> : undefined}>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {ACTIONS.map((a) => {
              const reason = a.blocked(s);
              const disabled = reason !== null || busy !== null;
              return (
                <div key={a.id} className="flex min-w-0 flex-col">
                  <button
                    type="button"
                    data-action={a.id}
                    disabled={disabled}
                    title={reason ?? a.description}
                    onClick={() => click(a)}
                    className={`cursor-pointer rounded border px-3 py-2.5 text-[12px] font-bold uppercase tracking-wider transition-colors disabled:cursor-not-allowed disabled:border-line disabled:bg-transparent disabled:text-dim ${styleCls[a.style]}`}
                  >
                    {busy === a.id ? 'Sending…' : a.label}
                  </button>
                  <p className="mt-1 px-0.5 text-[11px] text-mute">{reason ?? a.description}</p>
                </div>
              );
            })}
            <div className="flex min-w-0 flex-col">
              <a
                href="/api/report.html"
                target="_blank"
                rel="noopener noreferrer"
                data-action="export_report"
                className="rounded border border-line bg-raised px-3 py-2.5 text-center text-[12px] font-bold uppercase tracking-wider text-ink transition-colors hover:bg-line"
              >
                Export report
              </a>
              <p className="mt-1 px-0.5 text-[11px] text-mute">Opens the full performance report (HTML) in a new tab.</p>
            </div>
          </div>
        </Panel>

        <Panel title="Experiment & backend">
          <dl className="text-[12px]">
            {row('Status', label(st), false)}
            {row('Mode', text(exp?.mode ?? health.data?.mode), false)}
            {row('Started', dateTime(exp?.started_at))}
            {row('Ends', dateTime(exp?.ends_at))}
            {row('Duration', exp?.duration_days != null ? `${int(exp.duration_days)} days` : '—')}
            {row('Halt reason', text(exp?.halt_reason), false)}
            {row('Server time', dateTime(s?.server_time))}
            {row('Last state update', clockTime(live.lastUpdate))}
            {row('State feed', live.wsConnected ? 'WebSocket (live)' : live.unreachable ? 'Disconnected' : 'HTTP polling (3 s)', false)}
            {row('Backend version', text(health.data?.version))}
            {row('Health check', health.data === null ? (health.settled ? 'Unreachable' : 'Checking…') : health.error ? 'Failing' : health.data.ok === true ? 'OK' : health.data.ok === false ? 'Not OK' : '—', false)}
          </dl>
        </Panel>
      </div>

      {pending ? <ConfirmDialog def={pending} busy={busy !== null} onCancel={() => (busy === null ? setPending(null) : undefined)} onConfirm={() => void run(pending, true)} /> : null}
    </>
  );
}

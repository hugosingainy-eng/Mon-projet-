import { useCallback, useEffect, useRef, useState } from 'react';
import { useLiveState } from './api';
import { clockTime } from './format';
import { Header, type TabDef } from './Header';
import { Agents } from './sections/Agents';
import { Lab } from './sections/Lab';
import { Market } from './sections/Market';
import { PortfolioSection } from './sections/Portfolio';
import { Research } from './sections/Research';
import { SystemControls } from './sections/SystemControls';
import { Trading } from './sections/Trading';
import type { ControlResponse } from './types';

const TABS: TabDef[] = [
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'trading', label: 'Trading' },
  { id: 'market', label: 'Market' },
  { id: 'lab', label: 'Strategy Lab' },
  { id: 'agents', label: 'AI Agents' },
  { id: 'research', label: 'Research' },
  { id: 'system', label: 'System' },
];

function tabFromHash(): string {
  const h = location.hash.replace(/^#/, '');
  return TABS.some((t) => t.id === h) ? h : 'portfolio';
}

interface Toast extends ControlResponse {
  id: number;
  title: string;
}

export default function App() {
  const live = useLiveState();
  const [tab, setTab] = useState<string>(tabFromHash);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const select = useCallback((id: string) => {
    setTab(id);
    history.replaceState(null, '', `#${id}`);
    window.scrollTo({ top: 0 });
  }, []);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const notify = useCallback(
    (title: string, res: ControlResponse) => {
      const id = nextId.current++;
      setToasts((t) => [...t.slice(-3), { id, title, ...res }]);
      window.setTimeout(() => dismiss(id), res.ok ? 6000 : 10000);
    },
    [dismiss],
  );

  const s = live.state;

  return (
    <div className="min-h-screen">
      <Header live={live} tabs={TABS} active={tab} onSelect={select} />

      {live.unreachable ? (
        <div role="alert" data-testid="unreachable-banner" className="border-b border-neg/50 bg-neg/15 px-3 py-2 text-center text-[12.5px] font-medium text-neg sm:px-4">
          Backend unreachable — retrying automatically.{' '}
          {live.lastUpdate !== null
            ? `Values shown are the last ones received at ${clockTime(live.lastUpdate)} and may be out of date.`
            : 'No data has been received yet.'}
        </div>
      ) : null}

      <main className="mx-auto max-w-[1800px] space-y-3 px-3 py-3 sm:px-4">
        {tab === 'portfolio' ? <PortfolioSection portfolio={s?.portfolio ?? null} /> : null}
        {tab === 'trading' ? <Trading stats={s?.trading ?? null} /> : null}
        {tab === 'market' ? <Market /> : null}
        {tab === 'lab' ? <Lab lab={s?.lab ?? null} /> : null}
        {tab === 'agents' ? <Agents /> : null}
        {tab === 'research' ? <Research /> : null}
        {tab === 'system' ? <SystemControls live={live} notify={notify} /> : null}
      </main>

      <footer className="mx-auto max-w-[1800px] px-3 pt-2 pb-6 text-[11px] text-dim sm:px-4">
        Quantum Edge AI is a paper-trading research lab. All orders are simulated; no real money is ever traded. Nothing shown here is
        financial advice.
      </footer>

      <div className="pointer-events-none fixed inset-x-3 bottom-3 z-50 flex flex-col items-end gap-2 sm:left-auto sm:right-4 sm:w-[380px]" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            data-testid="toast"
            className={`pointer-events-auto flex w-full items-start gap-2 rounded-md border bg-raised px-3 py-2 shadow-lg shadow-black/50 ${
              t.ok ? 'border-pos/50' : 'border-neg/60'
            }`}
          >
            <span className={`mt-px text-[13px] font-bold ${t.ok ? 'text-pos' : 'text-neg'}`} aria-hidden="true">
              {t.ok ? '✓' : '✕'}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-mute">
                {t.title} · {t.ok ? 'OK' : 'Failed'}
              </div>
              <div className="break-words text-[12.5px] text-ink">{t.message}</div>
            </div>
            <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss notification" className="cursor-pointer px-1 text-mute hover:text-ink">
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

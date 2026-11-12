import { usePoll, usePollList } from '../api';
import { dateTime, int, isNum, label, num, pct, pnlClass, signedMoney, text } from '../format';
import type { DeployedStrategy, LabResult, LabState, LabSummary } from '../types';
import { type Col, DataTable, Empty, Loadable, Num, Panel, Pill, ProgressBar, StaleNote, Stat, type Tone } from '../ui';

const EVAL_TONE: Record<string, Tone> = {
  PASS: 'pos',
  FAIL_TRAIN: 'neg',
  FAIL_VALIDATION: 'neg',
  FAIL_TEST: 'neg',
  INSUFFICIENT_TRADES: 'warn',
};
const STAGE_TONE: Record<string, Tone> = { forward: 'accent', live: 'pos', retired: 'dim' };

function paramsText(p: Record<string, unknown> | null): string {
  if (!p || typeof p !== 'object') return '—';
  const parts = Object.entries(p).map(([k, v]) => `${k}=${typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)}`);
  return parts.length ? parts.join(', ') : '—';
}

const topCols: Col<LabResult>[] = [
  { key: 'rank', header: '#', align: 'right', cell: () => null },
  {
    key: 'strategy',
    header: 'Strategy',
    cell: (r) => (
      <div className="leading-tight">
        <div className="font-semibold text-ink">{text(r.strategy)}</div>
        <div className="max-w-[240px] truncate text-[10.5px] text-mute" title={paramsText(r.params)}>
          {paramsText(r.params)}
        </div>
      </div>
    ),
  },
  { key: 'instrument', header: 'Instrument', cell: (r) => text(r.instrument) },
  { key: 'tf', header: 'TF', cell: (r) => <span className="text-mute">{text(r.timeframe)}</span> },
  { key: 'method', header: 'Method', cell: (r) => <span className="text-mute">{label(r.method)}</span> },
  { key: 'eval', header: 'Evaluation', cell: (r) => (r.evaluation ? <Pill tone={EVAL_TONE[r.evaluation] ?? 'neutral'}>{label(r.evaluation)}</Pill> : <span className="text-dim">—</span>) },
  { key: 'score', header: 'Score', align: 'right', cell: (r) => <Num>{num(r.score)}</Num> },
  { key: 'trades', header: 'Trades', align: 'right', group: 'Whole period', cell: (r) => <Num>{int(r.trades)}</Num> },
  { key: 'ret', header: 'Net ret.', align: 'right', group: 'Whole period', cell: (r) => <Num className={pnlClass(r.net_return_pct)}>{pct(r.net_return_pct, true)}</Num> },
  { key: 'dd', header: 'Max DD', align: 'right', group: 'Whole period', cell: (r) => <Num>{pct(r.max_drawdown_pct)}</Num> },
  { key: 'sharpe', header: 'Sharpe', align: 'right', group: 'Whole period', cell: (r) => <Num>{num(r.sharpe)}</Num> },
  { key: 'sortino', header: 'Sortino', align: 'right', group: 'Whole period', cell: (r) => <Num>{num(r.sortino)}</Num> },
  { key: 'pf', header: 'PF', align: 'right', group: 'Whole period', cell: (r) => <Num>{num(r.profit_factor)}</Num> },
  { key: 'vret', header: 'Return', align: 'right', group: 'Validation', cell: (r) => <Num className={pnlClass(r.val_return_pct)}>{pct(r.val_return_pct, true)}</Num> },
  { key: 'vsharpe', header: 'Sharpe', align: 'right', group: 'Validation', cell: (r) => <Num>{num(r.val_sharpe)}</Num> },
  { key: 'tret', header: 'Return', align: 'right', group: 'Test', cell: (r) => <Num className={pnlClass(r.test_return_pct)}>{pct(r.test_return_pct, true)}</Num> },
  { key: 'tsharpe', header: 'Sharpe', align: 'right', group: 'Test', cell: (r) => <Num>{num(r.test_sharpe)}</Num> },
  { key: 'stab', header: 'Stability', align: 'right', group: 'Robustness', cell: (r) => <Num>{num(r.stability)}</Num> },
  { key: 'cost', header: 'Costs', align: 'right', group: 'Robustness', cell: (r) => <Num>{pct(r.cost_pct)}</Num> },
];

const stratCols: Col<DeployedStrategy>[] = [
  { key: 'strategy', header: 'Strategy', cell: (r) => <span className="font-semibold text-ink">{text(r.strategy)}</span> },
  { key: 'instrument', header: 'Instrument', cell: (r) => text(r.instrument) },
  { key: 'tf', header: 'TF', cell: (r) => <span className="text-mute">{text(r.timeframe)}</span> },
  { key: 'stage', header: 'Stage', cell: (r) => (r.stage ? <Pill tone={STAGE_TONE[r.stage] ?? 'neutral'}>{label(r.stage)}</Pill> : <span className="text-dim">—</span>) },
  { key: 'weight', header: 'Weight', align: 'right', cell: (r) => <Num>{num(r.weight)}</Num> },
  { key: 'ltrades', header: 'Live trades', align: 'right', cell: (r) => <Num>{int(r.live_trades)}</Num> },
  { key: 'lpnl', header: 'Live P&L', align: 'right', cell: (r) => <Num className={pnlClass(r.live_pnl_eur)}>{signedMoney(r.live_pnl_eur)}</Num> },
  { key: 'strades', header: 'Shadow trades', align: 'right', cell: (r) => <Num>{int(r.shadow_trades)}</Num> },
  { key: 'spnl', header: 'Shadow P&L', align: 'right', cell: (r) => <Num className={pnlClass(r.shadow_pnl_eur)}>{signedMoney(r.shadow_pnl_eur)}</Num> },
  { key: 'exp', header: 'Expected / trade', align: 'right', cell: (r) => <Num className={pnlClass(r.expected_trade_pct)}>{pct(r.expected_trade_pct, true)}</Num> },
  { key: 'expid', header: 'Experiment', align: 'right', cell: (r) => <Num className="text-mute">{text(r.experiment_id)}</Num> },
  { key: 'note', header: 'Note', cell: (r) => <span className="text-mute">{text(r.note)}</span>, className: 'max-w-[320px] truncate' },
  { key: 'updated', header: 'Updated', cell: (r) => <Num className="text-mute">{dateTime(r.updated_at)}</Num> },
];

function CountList({ title, counts, tones }: { title: string; counts: Record<string, number | null> | null | undefined; tones?: Record<string, Tone> }) {
  const entries = Object.entries(counts ?? {}).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
  const max = Math.max(0, ...entries.map(([, v]) => (isNum(v) ? v : 0)));
  return (
    <Panel title={title}>
      {entries.length === 0 ? (
        <p className="py-2 text-[12.5px] text-mute">No experiments recorded yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {entries.map(([k, v]) => {
            const tone = tones?.[k];
            const bar = tone === 'pos' ? 'bg-pos/70' : tone === 'neg' ? 'bg-neg/60' : tone === 'warn' ? 'bg-warn/60' : 'bg-accent/60';
            return (
              <li key={k}>
                <div className="flex items-baseline justify-between gap-3 text-[12px]">
                  <span className="truncate text-ink">{label(k)}</span>
                  <Num>{int(v)}</Num>
                </div>
                <div className="mt-0.5 h-1 overflow-hidden rounded-full bg-raised">
                  {isNum(v) && max > 0 ? <div className={`h-full rounded-full ${bar}`} style={{ width: `${(v / max) * 100}%` }} /> : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

export function Lab({ lab }: { lab: Partial<LabState> | null }) {
  const summary = usePoll<LabSummary>('/api/lab/summary', 5000, (v) => typeof v === 'object' && v !== null && !Array.isArray(v));
  const top = usePollList<LabResult>('/api/lab/top?limit=20');
  const strategies = usePollList<DeployedStrategy>('/api/strategies');

  const evalCounts = summary.data?.by_evaluation;
  // "Total" = every experiment the backend has stored, i.e. the sum of the per-evaluation counts.
  const total = evalCounts && Object.keys(evalCounts).length > 0 ? Object.values(evalCounts).reduce<number>((a, v) => a + (isNum(v) ? v : 0), 0) : null;
  const running = lab?.running;

  return (
    <>
      <Panel
        title="Strategy laboratory"
        right={
          typeof running === 'boolean' ? (
            <Pill tone={running ? 'pos' : 'neutral'}>{running ? 'Running' : 'Not running'}</Pill>
          ) : undefined
        }
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Total experiments stored" value={int(total)} sub="all runs, from summary" />
          <Stat label="Completed (this run)" value={int(lab?.completed)} />
          <Stat label="Target" value={int(lab?.target)} />
          <Stat label="Passed" value={int(lab?.passed)} className="text-pos" />
        </div>
        <div className="mt-3">
          <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-4 text-[11.5px] text-mute">
            <span>
              Progress{' '}
              <span className="num text-ink">
                {int(lab?.completed)} / {int(lab?.target)}
              </span>
            </span>
            <span className="num text-ink">{pct(lab?.progress_pct)}</span>
          </div>
          <ProgressBar value={isNum(lab?.progress_pct) ? lab.progress_pct : null} label="Experiment batch progress" tone="pos" />
        </div>
        <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1.5 text-[12px] sm:grid-cols-[auto_1fr]">
          <dt className="text-[10.5px] font-medium uppercase tracking-wider text-mute">Phase</dt>
          <dd className="text-ink">{label(lab?.phase)}</dd>
          <dt className="text-[10.5px] font-medium uppercase tracking-wider text-mute">Message</dt>
          <dd className="break-words text-ink">{text(lab?.message)}</dd>
          <dt className="text-[10.5px] font-medium uppercase tracking-wider text-mute">Last run</dt>
          <dd className="num text-ink">{dateTime(lab?.last_run_at)}</dd>
        </dl>
      </Panel>

      {summary.data === null ? (
        <Panel title="Experiment breakdown">
          <Loadable polled={summary} what="lab summary">
            {() => null}
          </Loadable>
        </Panel>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <CountList title="By evaluation" counts={summary.data.by_evaluation} tones={EVAL_TONE} />
          <CountList title="By search method" counts={summary.data.by_method} />
          <CountList title="By strategy family" counts={summary.data.by_family} />
        </div>
      )}

      <Panel title="Top 20 experiments" flush right={<><StaleNote polled={top} /><span>ranked by weakest-segment Sharpe × stability</span></>}>
        <Loadable polled={top} what="top experiments">
          {(rows) =>
            rows.length === 0 ? (
              <Empty>No experiment results yet. Run the experiment batch from the System tab.</Empty>
            ) : (
              <DataTable
                cols={topCols.map((c) => (c.key === 'rank' ? { ...c, cell: (r: LabResult) => <Num className="text-mute">{String(rows.indexOf(r) + 1)}</Num> } : c))}
                rows={rows}
                rowKey={(r, i) => `${r.id}-${i}`}
                empty=""
                maxHeight={620}
              />
            )
          }
        </Loadable>
      </Panel>

      <Panel title="Deployed strategies" flush right={<StaleNote polled={strategies} />}>
        <Loadable polled={strategies} what="deployed strategies">
          {(rows) => <DataTable cols={stratCols} rows={rows} rowKey={(r, i) => `${r.id}-${i}`} empty="No strategies deployed yet." maxHeight={480} />}
        </Loadable>
      </Panel>
    </>
  );
}

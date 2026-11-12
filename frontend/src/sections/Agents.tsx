import { usePollList } from '../api';
import { dateTime, fractionPct, int, isNum, label, money, text } from '../format';
import type { Agent, Decision, Incident, Signal } from '../types';
import { type Col, DataTable, Empty, Flag, Loadable, Num, Panel, Pill, SideTag, StaleNote, type Tone } from '../ui';

const AGENT_TONE: Record<string, Tone> = { idle: 'neutral', running: 'accent', ok: 'pos', error: 'neg', disabled: 'dim' };
const SEVERITY_TONE: Record<string, Tone> = { info: 'accent', warning: 'warn', error: 'neg' };

function AgentCard({ a }: { a: Agent }) {
  const status = a.status ?? '';
  const hasErrors = isNum(a.errors) && a.errors > 0;
  return (
    <article className={`min-w-0 rounded-md border bg-panel p-3 ${status === 'error' ? 'border-neg/50' : 'border-line'} ${status === 'disabled' ? 'opacity-70' : ''}`} data-testid="agent-card">
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 break-words text-[13px] font-semibold text-ink">{text(a.name)}</h3>
        {status ? <Pill tone={AGENT_TONE[status] ?? 'neutral'}>{label(status)}</Pill> : <span className="text-dim">—</span>}
      </div>
      <p className="mt-0.5 text-[11.5px] text-mute">{text(a.role)}</p>
      <dl className="mt-2 space-y-1 border-t border-line pt-2 text-[11.5px]">
        <div className="flex justify-between gap-3">
          <dt className="text-mute">Last run</dt>
          <dd className="num text-right text-ink">{dateTime(a.last_run)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="shrink-0 text-mute">Activity</dt>
          <dd className="min-w-0 break-words text-right text-ink">{text(a.activity)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-mute">Errors</dt>
          <dd className={`num ${hasErrors ? 'text-neg' : 'text-ink'}`}>{int(a.errors)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="shrink-0 text-mute">Last error</dt>
          <dd className={`min-w-0 break-words text-right ${a.last_error ? 'text-neg' : 'text-dim'}`}>{text(a.last_error)}</dd>
        </div>
      </dl>
    </article>
  );
}

const wrap = 'min-w-[220px] max-w-[520px] whitespace-normal break-words';

const signalCols: Col<Signal>[] = [
  { key: 'ts', header: 'Time', cell: (r) => <Num className="text-mute">{dateTime(r.ts)}</Num> },
  { key: 'agent', header: 'Agent', cell: (r) => text(r.agent) },
  { key: 'instrument', header: 'Instrument', cell: (r) => <span className="font-semibold text-ink">{text(r.instrument)}</span> },
  { key: 'dir', header: 'Direction', cell: (r) => <SideTag side={r.direction} /> },
  { key: 'conf', header: 'Confidence', align: 'right', cell: (r) => <Num>{fractionPct(r.confidence)}</Num> },
  { key: 'summary', header: 'Summary', cell: (r) => <span className="text-mute">{text(r.summary)}</span>, className: wrap },
];

const decisionCols: Col<Decision>[] = [
  { key: 'ts', header: 'Time', cell: (r) => <Num className="text-mute">{dateTime(r.ts)}</Num> },
  { key: 'instrument', header: 'Instrument', cell: (r) => <span className="font-semibold text-ink">{text(r.instrument)}</span> },
  { key: 'side', header: 'Side', cell: (r) => <SideTag side={r.side} /> },
  { key: 'strategy', header: 'Strategy', cell: (r) => <span className="text-mute">{text(r.strategy)}</span> },
  { key: 'approved', header: 'Decision', cell: (r) => <Flag value={r.approved} yes="Approved" no="Rejected" yesTone="pos" noTone="neg" /> },
  { key: 'notional', header: 'Notional', align: 'right', cell: (r) => <Num>{money(r.notional_eur)}</Num> },
  { key: 'reason', header: 'Reason', cell: (r) => <span className="text-mute">{text(r.reason)}</span>, className: wrap },
];

const incidentCols: Col<Incident>[] = [
  { key: 'ts', header: 'Time', cell: (r) => <Num className="text-mute">{dateTime(r.ts)}</Num> },
  { key: 'sev', header: 'Severity', cell: (r) => (r.severity ? <Pill tone={SEVERITY_TONE[r.severity] ?? 'neutral'}>{r.severity}</Pill> : <span className="text-dim">—</span>) },
  { key: 'component', header: 'Component', cell: (r) => text(r.component) },
  { key: 'message', header: 'Message', cell: (r) => <span className="text-mute">{text(r.message)}</span>, className: wrap },
  { key: 'recovered', header: 'Recovered', cell: (r) => <Flag value={r.recovered} yes="Recovered" no="Open" yesTone="pos" noTone="warn" /> },
];

export function Agents() {
  const agents = usePollList<Agent>('/api/agents');
  const signals = usePollList<Signal>('/api/signals?limit=100');
  const decisions = usePollList<Decision>('/api/decisions?limit=100');
  const incidents = usePollList<Incident>('/api/incidents?limit=100');

  return (
    <>
      <Panel
        title="AI agents"
        right={
          <>
            <StaleNote polled={agents} />
            {agents.data ? <span className="num">{agents.data.length} agents</span> : null}
          </>
        }
      >
        <Loadable polled={agents} what="agents">
          {(rows) =>
            rows.length === 0 ? (
              <Empty>No agents reported by the backend.</Empty>
            ) : (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                {rows.map((a, i) => (
                  <AgentCard key={`${a.id}-${i}`} a={a} />
                ))}
              </div>
            )
          }
        </Loadable>
      </Panel>

      <Panel title="Recent signals" flush right={<StaleNote polled={signals} />}>
        <Loadable polled={signals} what="signals">
          {(rows) => <DataTable cols={signalCols} rows={rows} rowKey={(r, i) => `${r.ts}-${i}`} empty="No signals yet." maxHeight={400} />}
        </Loadable>
      </Panel>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Panel title="Risk decisions" flush right={<StaleNote polled={decisions} />}>
          <Loadable polled={decisions} what="risk decisions">
            {(rows) => <DataTable cols={decisionCols} rows={rows} rowKey={(r, i) => `${r.ts}-${i}`} empty="No risk decisions yet." maxHeight={400} />}
          </Loadable>
        </Panel>
        <Panel title="Incidents" flush right={<StaleNote polled={incidents} />}>
          <Loadable polled={incidents} what="incidents">
            {(rows) => <DataTable cols={incidentCols} rows={rows} rowKey={(r, i) => `${r.ts}-${i}`} empty="No incidents recorded." maxHeight={400} />}
          </Loadable>
        </Panel>
      </div>
    </>
  );
}

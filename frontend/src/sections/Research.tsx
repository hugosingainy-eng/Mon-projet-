import { usePoll, usePollList } from '../api';
import { compact, dateOnly, dateTime, int, isNum, label, num, safeUrl, text } from '../format';
import type { Elite, EliteFiling, EliteHolding, NewsItem } from '../types';
import { type Col, DataTable, Empty, ExtLink, Loadable, Num, Panel, Pill, StaleNote } from '../ui';

function sentimentClass(v: number | null): string {
  if (!isNum(v) || v === 0) return 'text-mute';
  return v > 0 ? 'text-pos' : 'text-neg';
}

function SourceRef({ value }: { value: string | null }) {
  const url = safeUrl(value);
  if (url) return <ExtLink href={url}>source</ExtLink>;
  return <span className="text-mute">{text(value)}</span>;
}

const usd = (v: number | null) => (isNum(v) ? `$${compact(v)}` : '—');
const age = (v: number | null) => (isNum(v) ? `${int(v)} d` : '—');

const filingCols: Col<EliteFiling>[] = [
  { key: 'inst', header: 'Institution', cell: (r) => <span className="font-semibold text-ink">{text(r.institution)}</span> },
  { key: 'form', header: 'Form', cell: (r) => <span className="text-mute">{text(r.form)}</span> },
  { key: 'report', header: 'Report date', cell: (r) => <Num>{dateOnly(r.report_date)}</Num> },
  { key: 'filed', header: 'Filed', cell: (r) => <Num>{dateOnly(r.filing_date)}</Num> },
  { key: 'age', header: 'Report age', align: 'right', cell: (r) => <Num className="text-warn">{age(r.freshness_days)}</Num> },
  { key: 'url', header: 'Source', cell: (r) => <SourceRef value={r.url} /> },
];

const holdingCols: Col<EliteHolding>[] = [
  { key: 'inst', header: 'Institution', cell: (r) => <span className="font-semibold text-ink">{text(r.institution)}</span> },
  { key: 'issuer', header: 'Issuer', cell: (r) => text(r.issuer) },
  { key: 'value', header: 'Reported value (USD)', align: 'right', cell: (r) => <Num>{usd(r.value_usd)}</Num> },
  { key: 'shares', header: 'Shares', align: 'right', cell: (r) => <Num>{int(r.shares)}</Num> },
  { key: 'report', header: 'Report date', cell: (r) => <Num>{dateOnly(r.report_date)}</Num> },
  { key: 'filed', header: 'Filed', cell: (r) => <Num>{dateOnly(r.filing_date)}</Num> },
  { key: 'age', header: 'Report age', align: 'right', cell: (r) => <Num className="text-warn">{age(r.freshness_days)}</Num> },
  { key: 'conf', header: 'Confidence', cell: (r) => (r.confidence ? <Pill>{label(r.confidence)}</Pill> : <span className="text-dim">—</span>) },
  { key: 'source', header: 'Source', cell: (r) => <SourceRef value={r.source} /> },
];

function News() {
  const news = usePollList<NewsItem>('/api/news?limit=50');
  return (
    <Panel title="News" flush right={<StaleNote polled={news} />}>
      <Loadable polled={news} what="news">
        {(rows) =>
          rows.length === 0 ? (
            <Empty>No news collected yet.</Empty>
          ) : (
            <ul className="max-h-[640px] divide-y divide-line/60 overflow-y-auto">
              {rows.map((n, i) => {
                const url = safeUrl(n.url);
                return (
                  <li key={`${n.ts}-${i}`} className="px-3 py-2" data-testid="news-item">
                    <div className="break-words text-[12.5px] font-medium text-ink">{url ? <ExtLink href={url}>{text(n.title)}</ExtLink> : text(n.title)}</div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-mute">
                      <span>Source: {text(n.publisher)}</span>
                      <span className="text-dim">·</span>
                      <time className="num" dateTime={n.ts ?? undefined}>
                        {dateTime(n.ts)}
                      </time>
                      {n.instrument ? (
                        <>
                          <span className="text-dim">·</span>
                          <span className="font-semibold text-ink">{n.instrument}</span>
                        </>
                      ) : null}
                      <span className="text-dim">·</span>
                      <span>
                        sentiment <span className={`num ${sentimentClass(n.sentiment)}`}>{num(n.sentiment, 2, true)}</span>
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )
        }
      </Loadable>
    </Panel>
  );
}

export function Research() {
  const elite = usePoll<Elite>('/api/elite', 5000, (v) => typeof v === 'object' && v !== null && !Array.isArray(v));

  return (
    <>
      <News />

      <Panel title="Elite Trader Intelligence" right={<StaleNote polled={elite} />}>
        <p role="note" data-testid="delay-note" className="mb-3 rounded border border-warn/50 bg-warn/10 px-3 py-2 text-[12px] text-warn">
          <strong className="font-semibold">Delayed data.</strong> 13F disclosures are filed weeks after the end of each quarter. The holdings below are
          historical snapshots as of their report date — they are <strong className="font-semibold">not current positions</strong> and must not be read as
          what these institutions hold today.
        </p>
        <Loadable polled={elite} what="elite trader intelligence">
          {(e) => {
            const principles = Array.isArray(e.principles) ? e.principles : [];
            const filings = Array.isArray(e.filings) ? e.filings : [];
            const holdings = Array.isArray(e.holdings) ? e.holdings : [];
            return (
              <div className="space-y-4">
                <div>
                  <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-mute">Principles</h3>
                  {principles.length === 0 ? (
                    <p className="text-[12.5px] text-mute">No principles available yet.</p>
                  ) : (
                    <ul className="grid grid-cols-1 gap-2 md:grid-cols-2 2xl:grid-cols-3">
                      {principles.map((p, i) => (
                        <li key={i} className="min-w-0 rounded-md border border-line bg-raised/50 p-3">
                          <div className="text-[12.5px] font-semibold text-ink">{text(p.trader)}</div>
                          <p className="mt-1 break-words text-[12px] text-ink/90">{text(p.principle)}</p>
                          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
                            {(Array.isArray(p.families) ? p.families : []).map((f) => (
                              <Pill key={f} tone="accent">
                                {label(f)}
                              </Pill>
                            ))}
                            <span className="ml-auto">
                              <SourceRef value={p.source} />
                            </span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div>
                  <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-mute">Filings</h3>
                  <div className="rounded-md border border-line">
                    <DataTable cols={filingCols} rows={filings} rowKey={(_, i) => String(i)} empty="No filings retrieved yet." maxHeight={360} />
                  </div>
                </div>

                <div>
                  <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-mute">
                    Disclosed holdings <span className="font-normal normal-case tracking-normal text-warn">— delayed, as of report date</span>
                  </h3>
                  <div className="rounded-md border border-line">
                    <DataTable cols={holdingCols} rows={holdings} rowKey={(_, i) => String(i)} empty="No holdings retrieved yet." maxHeight={480} />
                  </div>
                </div>
              </div>
            );
          }}
        </Loadable>
      </Panel>
    </>
  );
}

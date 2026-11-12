import { useMemo, useState } from 'react';
import { usePollList } from '../api';
import { compact, dateTime, label, pct, pnlClass, price, text } from '../format';
import type { MarketRow } from '../types';
import { type Col, DataTable, Flag, Loadable, Num, Panel, Pill, StaleNote, type Tone } from '../ui';

const REGIME_TONE: Record<string, Tone> = { trend_up: 'pos', trend_down: 'neg', range: 'neutral', volatile: 'warn' };

const cols: Col<MarketRow>[] = [
  {
    key: 'instrument',
    header: 'Instrument',
    cell: (r) => (
      <div className="leading-tight">
        <div className="font-semibold text-ink">{text(r.instrument)}</div>
        <div className="max-w-[200px] truncate text-[10.5px] text-mute">{text(r.name)}</div>
      </div>
    ),
  },
  { key: 'class', header: 'Asset class', cell: (r) => <span className="text-mute">{label(r.asset_class)}</span> },
  { key: 'price', header: 'Price', align: 'right', cell: (r) => <Num>{price(r.price)}</Num> },
  { key: 'bid', header: 'Bid', align: 'right', cell: (r) => <Num className="text-mute">{price(r.bid)}</Num> },
  { key: 'ask', header: 'Ask', align: 'right', cell: (r) => <Num className="text-mute">{price(r.ask)}</Num> },
  { key: 'chg', header: 'Change', align: 'right', cell: (r) => <Num className={pnlClass(r.change_pct)}>{pct(r.change_pct, true)}</Num> },
  { key: 'vol', header: 'Volume', align: 'right', cell: (r) => <Num>{compact(r.volume)}</Num> },
  { key: 'volat', header: 'Volatility', align: 'right', cell: (r) => <Num>{pct(r.volatility_pct)}</Num> },
  {
    key: 'regime',
    header: 'Regime',
    cell: (r) => (r.regime ? <Pill tone={REGIME_TONE[r.regime] ?? 'neutral'}>{label(r.regime)}</Pill> : <span className="text-dim">—</span>),
  },
  { key: 'provider', header: 'Provider', cell: (r) => <span className="text-mute">{text(r.provider)}</span> },
  { key: 'update', header: 'Last update', cell: (r) => <Num className="text-mute">{dateTime(r.last_update)}</Num> },
  { key: 'open', header: 'Market', cell: (r) => <Flag value={r.market_open} yes="Open" no="Closed" /> },
  { key: 'stale', header: 'Data', cell: (r) => <Flag value={r.stale} yes="Stale" no="Fresh" yesTone="warn" noTone="pos" /> },
  { key: 'tradable', header: 'Tradable', cell: (r) => <Flag value={r.tradable} yes="Tradable" no="Watch only" yesTone="accent" /> },
];

export function Market() {
  const market = usePollList<MarketRow>('/api/market');
  const [filter, setFilter] = useState<string>('all');

  const classes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of market.data ?? []) {
      const c = r.asset_class || 'unknown';
      counts.set(c, (counts.get(c) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [market.data]);

  const active = filter === 'all' || classes.some(([c]) => c === filter) ? filter : 'all';
  const rows = useMemo(
    () => (market.data ?? []).filter((r) => active === 'all' || (r.asset_class || 'unknown') === active),
    [market.data, active],
  );

  const chip = (id: string, text_: string, count: number) => {
    const on = active === id;
    return (
      <button
        key={id}
        type="button"
        aria-pressed={on}
        data-filter={id}
        onClick={() => setFilter(id)}
        className={`cursor-pointer rounded border px-2 py-1 text-[11px] font-medium capitalize whitespace-nowrap ${
          on ? 'border-accent/60 bg-accent/15 text-accent' : 'border-line bg-raised text-mute hover:text-ink'
        }`}
      >
        {text_} <span className="num opacity-70">{count}</span>
      </button>
    );
  };

  return (
    <Panel title="Market monitoring" flush right={<StaleNote polled={market} />}>
      <Loadable polled={market} what="market data">
        {(all) => (
          <>
            {all.length > 0 ? (
              <div className="flex flex-wrap items-center gap-1.5 border-b border-line px-3 py-2" role="group" aria-label="Asset class filter">
                <span className="mr-1 text-[10.5px] font-medium uppercase tracking-wider text-mute">Asset class</span>
                {chip('all', 'All', all.length)}
                {classes.map(([c, n]) => chip(c, label(c), n))}
              </div>
            ) : null}
            <DataTable
              cols={cols}
              rows={rows}
              rowKey={(r, i) => `${r.instrument}-${i}`}
              empty={all.length === 0 ? 'No market data yet. Instruments appear once a data provider returns quotes.' : 'No instruments in this asset class.'}
              rowClass={(r) => (r.stale ? 'opacity-70' : '')}
            />
          </>
        )}
      </Loadable>
    </Panel>
  );
}

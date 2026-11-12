import { usePollList } from '../api';
import { dateTime, fractionPct, int, label, minutes, money, num, pct, pnlClass, price, qty, signedMoney, text } from '../format';
import type { Position, Trade, TradingStats } from '../types';
import { type Col, DataTable, Loadable, Num, Panel, SideTag, StaleNote, Stat } from '../ui';

const instrumentCell = (r: { instrument: string | null; name?: string | null; asset_class: string | null }) => (
  <div className="leading-tight">
    <div className="font-semibold text-ink">{text(r.instrument)}</div>
    <div className="max-w-[180px] truncate text-[10.5px] text-mute">{[r.name, r.asset_class].filter(Boolean).join(' · ') || '—'}</div>
  </div>
);

const positionCols: Col<Position>[] = [
  { key: 'instrument', header: 'Instrument', cell: instrumentCell },
  { key: 'side', header: 'Side', cell: (r) => <SideTag side={r.side} /> },
  { key: 'qty', header: 'Qty', align: 'right', cell: (r) => <Num>{qty(r.qty)}</Num> },
  { key: 'entry', header: 'Entry', align: 'right', cell: (r) => <Num>{price(r.entry_price)}</Num> },
  { key: 'current', header: 'Current', align: 'right', cell: (r) => <Num>{price(r.current_price)}</Num> },
  { key: 'ccy', header: 'Ccy', cell: (r) => <span className="text-mute">{text(r.currency)}</span> },
  { key: 'notional', header: 'Entry notional', align: 'right', cell: (r) => <Num>{money(r.entry_notional_eur)}</Num> },
  { key: 'value', header: 'Value', align: 'right', cell: (r) => <Num>{money(r.value_eur)}</Num> },
  { key: 'upnl', header: 'Unrealized P&L', align: 'right', cell: (r) => <Num className={pnlClass(r.unrealized_pnl_eur)}>{signedMoney(r.unrealized_pnl_eur)}</Num> },
  { key: 'upct', header: 'P&L %', align: 'right', cell: (r) => <Num className={pnlClass(r.unrealized_pct)}>{pct(r.unrealized_pct, true)}</Num> },
  { key: 'stop', header: 'Stop', align: 'right', cell: (r) => <Num>{price(r.stop_price)}</Num> },
  { key: 'tp', header: 'Take profit', align: 'right', cell: (r) => <Num>{price(r.take_profit)}</Num> },
  { key: 'strategy', header: 'Strategy', cell: (r) => <span className="text-mute">{text(r.strategy)}</span> },
  { key: 'opened', header: 'Opened', cell: (r) => <Num className="text-mute">{dateTime(r.opened_at)}</Num> },
];

const tradeCols: Col<Trade>[] = [
  { key: 'closed', header: 'Closed', cell: (r) => <Num className="text-mute">{dateTime(r.closed_at)}</Num> },
  { key: 'instrument', header: 'Instrument', cell: instrumentCell },
  { key: 'side', header: 'Side', cell: (r) => <SideTag side={r.side} /> },
  { key: 'qty', header: 'Qty', align: 'right', cell: (r) => <Num>{qty(r.qty)}</Num> },
  { key: 'entry', header: 'Entry', align: 'right', cell: (r) => <Num>{price(r.entry_price)}</Num> },
  { key: 'exit', header: 'Exit', align: 'right', cell: (r) => <Num>{price(r.exit_price)}</Num> },
  { key: 'ccy', header: 'Ccy', cell: (r) => <span className="text-mute">{text(r.currency)}</span> },
  { key: 'pnl', header: 'Net P&L', align: 'right', cell: (r) => <Num className={pnlClass(r.pnl_eur)}>{signedMoney(r.pnl_eur)}</Num> },
  { key: 'pnlpct', header: 'P&L %', align: 'right', cell: (r) => <Num className={pnlClass(r.pnl_pct)}>{pct(r.pnl_pct, true)}</Num> },
  { key: 'fees', header: 'Fees', align: 'right', cell: (r) => <Num>{money(r.fees_eur)}</Num> },
  { key: 'slip', header: 'Slippage', align: 'right', cell: (r) => <Num>{money(r.slippage_eur)}</Num> },
  { key: 'fx', header: 'FX cost', align: 'right', cell: (r) => <Num>{money(r.fx_cost_eur)}</Num> },
  { key: 'dur', header: 'Duration', align: 'right', cell: (r) => <Num>{minutes(r.duration_minutes)}</Num> },
  { key: 'reason', header: 'Exit reason', cell: (r) => <span className="text-mute">{label(r.exit_reason)}</span> },
  { key: 'strategy', header: 'Strategy', cell: (r) => <span className="text-mute">{text(r.strategy)}</span> },
  { key: 'opened', header: 'Opened', cell: (r) => <Num className="text-mute">{dateTime(r.opened_at)}</Num> },
];

export function Trading({ stats }: { stats: Partial<TradingStats> | null }) {
  const positions = usePollList<Position>('/api/positions');
  const trades = usePollList<Trade>('/api/trades?limit=200');
  const t = stats;

  return (
    <>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 2xl:grid-cols-8">
        <Stat label="Open positions" value={int(t?.open_positions)} />
        <Stat label="Closed trades" value={int(t?.closed_trades)} />
        <Stat label="Wins" value={int(t?.wins)} className="text-pos" />
        <Stat label="Losses" value={int(t?.losses)} className="text-neg" />
        <Stat label="Win rate" value={fractionPct(t?.win_rate)} />
        <Stat label="Profit factor" value={num(t?.profit_factor)} />
        <Stat label="Avg duration" value={minutes(t?.avg_duration_minutes)} />
        <Stat label="Expectancy / trade" value={signedMoney(t?.expectancy)} className={pnlClass(t?.expectancy)} />
      </div>

      <Panel
        title="Open positions"
        flush
        right={
          <>
            <StaleNote polled={positions} />
            {positions.data ? <span className="num">{positions.data.length} open</span> : null}
          </>
        }
      >
        <Loadable polled={positions} what="open positions">
          {(rows) => <DataTable cols={positionCols} rows={rows} rowKey={(r, i) => `${r.id}-${i}`} empty="No open positions." maxHeight={420} />}
        </Loadable>
      </Panel>

      <Panel
        title="Closed trades"
        flush
        right={
          <>
            <StaleNote polled={trades} />
            {trades.data ? <span className="num">{trades.data.length} shown · newest first · P&L net of all costs</span> : null}
          </>
        }
      >
        <Loadable polled={trades} what="closed trades">
          {(rows) => <DataTable cols={tradeCols} rows={rows} rowKey={(r, i) => `${r.id}-${i}`} empty="No trades yet." maxHeight={560} />}
        </Loadable>
      </Panel>
    </>
  );
}

import { useMemo } from 'react';
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { usePollList } from '../api';
import { compact, dateTime, isNum, money, pct, pnlClass, signedMoney, tsMillis } from '../format';
import type { EquityPoint, Portfolio } from '../types';
import { Empty, Loadable, Panel, StaleNote, Stat, StatGrid } from '../ui';

interface ChartPoint {
  t: number;
  equity: number | null;
  cash: number | null;
}

interface TipProps {
  active?: boolean;
  payload?: { payload?: ChartPoint }[];
}

function ChartTip({ active, payload, currency }: TipProps & { currency: string | null }) {
  const p = active ? payload?.[0]?.payload : undefined;
  if (!p) return null;
  return (
    <div className="rounded border border-line bg-raised px-2.5 py-1.5 text-[11.5px] shadow-lg shadow-black/50">
      <div className="mb-1 text-mute">{dateTime(new Date(p.t).toISOString())}</div>
      <div className="flex justify-between gap-4">
        <span className="text-accent">Equity</span>
        <span className="num text-ink">{money(p.equity, currency)}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-mute">Cash</span>
        <span className="num text-ink">{money(p.cash, currency)}</span>
      </div>
    </div>
  );
}

function EquityChart({ points, initial, currency }: { points: EquityPoint[]; initial: number | null; currency: string | null }) {
  const data = useMemo<ChartPoint[]>(() => {
    const out: ChartPoint[] = [];
    for (const p of points) {
      const t = tsMillis(p.ts);
      if (t === null) continue;
      out.push({ t, equity: isNum(p.equity) ? p.equity : null, cash: isNum(p.cash) ? p.cash : null });
    }
    return out;
  }, [points]);

  if (data.length === 0) return <Empty>No equity history yet. The curve appears once the experiment records its first snapshot.</Empty>;

  const first = data[0]!.t;
  const last = data[data.length - 1]!.t;
  const spanMs = last - first;
  const tick = (t: number) => {
    const d = new Date(t);
    return spanMs > 36 * 3600 * 1000
      ? d.toLocaleString(undefined, { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
      : d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false });
  };
  const sparse = data.length < 3;

  return (
    <div>
      <div className="mb-1 flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-[11px] text-mute">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 bg-accent" /> Equity
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0 w-4 border-t-2 border-dashed border-mute" /> Cash
        </span>
        {isNum(initial) ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-0 w-4 border-t border-dotted border-warn" /> Initial capital
          </span>
        ) : null}
        <span className="ml-auto num">{data.length} points</span>
      </div>
      <div className="h-[260px] w-full sm:h-[340px]" data-testid="equity-chart">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#4cc2ff" stopOpacity={0.28} />
                <stop offset="100%" stopColor="#4cc2ff" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1e2938" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              tickFormatter={tick}
              tick={{ fill: '#8796a8', fontSize: 10.5 }}
              stroke="#1e2938"
              tickLine={false}
              minTickGap={48}
            />
            <YAxis
              domain={['auto', 'auto']}
              tickFormatter={(v: number) => compact(v)}
              tick={{ fill: '#8796a8', fontSize: 10.5 }}
              stroke="#1e2938"
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <Tooltip
              isAnimationActive={false}
              cursor={{ stroke: '#5d6a7a', strokeDasharray: '3 3' }}
              content={(p) => <ChartTip {...(p as unknown as TipProps)} currency={currency} />}
            />
            {isNum(initial) ? <ReferenceLine y={initial} stroke="#f5b83d" strokeDasharray="1 4" ifOverflow="extendDomain" /> : null}
            <Area
              type="monotone"
              dataKey="equity"
              stroke="#4cc2ff"
              strokeWidth={1.75}
              fill="url(#eqFill)"
              dot={sparse ? { r: 3, fill: '#4cc2ff', strokeWidth: 0 } : false}
              activeDot={{ r: 3.5 }}
              isAnimationActive={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="cash"
              stroke="#8796a8"
              strokeWidth={1.25}
              strokeDasharray="5 4"
              dot={sparse ? { r: 2.5, fill: '#8796a8', strokeWidth: 0 } : false}
              activeDot={{ r: 3 }}
              isAnimationActive={false}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function PortfolioSection({ portfolio }: { portfolio: Partial<Portfolio> | null }) {
  const equity = usePollList<EquityPoint>('/api/equity');
  const p = portfolio;
  const cur = p?.currency ?? null;
  const cost = (v: unknown) => (isNum(v) && v !== 0 ? 'text-warn' : 'text-ink');

  return (
    <>
      <StatGrid>
        <Stat label="Initial capital" value={money(p?.initial_capital, cur)} />
        <Stat label="Equity" value={money(p?.equity, cur)} />
        <Stat label="Cash" value={money(p?.cash, cur)} />
        <Stat label="Invested" value={money(p?.invested, cur)} />
        <Stat label="Positions value" value={money(p?.positions_value, cur)} />
        <Stat label="Realized P&L" value={signedMoney(p?.realized_pnl, cur)} className={pnlClass(p?.realized_pnl)} />
        <Stat label="Unrealized P&L" value={signedMoney(p?.unrealized_pnl, cur)} className={pnlClass(p?.unrealized_pnl)} />
        <Stat label="Total return" value={pct(p?.total_return_pct, true)} className={pnlClass(p?.total_return_pct)} />
        <Stat label="Daily return" value={pct(p?.daily_return_pct, true)} className={pnlClass(p?.daily_return_pct)} />
        <Stat label="Max drawdown" value={pct(p?.max_drawdown_pct)} className={isNum(p?.max_drawdown_pct) && p.max_drawdown_pct !== 0 ? 'text-neg' : 'text-ink'} />
        <Stat label="Fees paid" value={money(p?.fees, cur)} className={cost(p?.fees)} />
        <Stat label="Slippage" value={money(p?.slippage, cur)} className={cost(p?.slippage)} />
        <Stat label="FX costs" value={money(p?.fx_costs, cur)} className={cost(p?.fx_costs)} />
      </StatGrid>

      <Panel title="Equity curve" right={<StaleNote polled={equity} />}>
        <Loadable polled={equity} what="equity history">
          {(points) => <EquityChart points={points} initial={isNum(p?.initial_capital) ? p.initial_capital : null} currency={cur} />}
        </Loadable>
      </Panel>
    </>
  );
}

// Types mirror docs/API.md. Every numeric field may be null (value unavailable).

export type N = number | null;
export type S = string | null;

export type ExperimentStatus = 'idle' | 'running' | 'paused' | 'stopped' | 'halted' | 'completed';

export interface Experiment {
  status: ExperimentStatus | string;
  mode: S;
  started_at: S;
  ends_at: S;
  duration_days: N;
  elapsed_seconds: N;
  remaining_seconds: N;
  halt_reason: S;
}

export interface Portfolio {
  currency: S;
  initial_capital: N;
  equity: N;
  cash: N;
  invested: N;
  positions_value: N;
  realized_pnl: N;
  unrealized_pnl: N;
  fees: N;
  slippage: N;
  fx_costs: N;
  total_return_pct: N;
  daily_return_pct: N;
  max_drawdown_pct: N;
}

export interface TradingStats {
  open_positions: N;
  closed_trades: N;
  wins: N;
  losses: N;
  win_rate: N;
  profit_factor: N;
  avg_duration_minutes: N;
  expectancy: N;
}

export interface LabState {
  running: boolean | null;
  target: N;
  completed: N;
  passed: N;
  progress_pct: N;
  phase: S;
  last_run_at: S;
  message: S;
}

export interface AppState {
  server_time?: S;
  experiment?: Partial<Experiment> | null;
  portfolio?: Partial<Portfolio> | null;
  trading?: Partial<TradingStats> | null;
  lab?: Partial<LabState> | null;
}

export interface Position {
  id: string | number;
  instrument: S;
  name: S;
  asset_class: S;
  side: S;
  qty: N;
  entry_price: N;
  current_price: N;
  currency: S;
  entry_notional_eur: N;
  value_eur: N;
  unrealized_pnl_eur: N;
  unrealized_pct: N;
  stop_price: N;
  take_profit: N;
  strategy_id: string | number | null;
  strategy: S;
  opened_at: S;
}

export interface Trade {
  id: string | number;
  instrument: S;
  asset_class: S;
  side: S;
  qty: N;
  entry_price: N;
  exit_price: N;
  currency: S;
  pnl_eur: N;
  pnl_pct: N;
  fees_eur: N;
  slippage_eur: N;
  fx_cost_eur: N;
  opened_at: S;
  closed_at: S;
  duration_minutes: N;
  exit_reason: S;
  strategy: S;
}

export interface EquityPoint {
  ts: S;
  equity: N;
  cash: N;
}

export interface MarketRow {
  instrument: S;
  name: S;
  asset_class: S;
  tradable: boolean | null;
  price: N;
  bid: N;
  ask: N;
  change_pct: N;
  volume: N;
  volatility_pct: N;
  regime: S;
  provider: S;
  last_update: S;
  market_open: boolean | null;
  stale: boolean | null;
}

export interface LabResult {
  id: string | number;
  strategy: S;
  instrument: S;
  timeframe: S;
  method: S;
  params: Record<string, unknown> | null;
  trades: N;
  net_return_pct: N;
  max_drawdown_pct: N;
  sharpe: N;
  sortino: N;
  profit_factor: N;
  val_return_pct: N;
  val_sharpe: N;
  test_return_pct: N;
  test_sharpe: N;
  stability: N;
  cost_pct: N;
  evaluation: S;
  score: N;
}

export interface LabSummary {
  by_evaluation?: Record<string, number | null> | null;
  by_method?: Record<string, number | null> | null;
  by_family?: Record<string, number | null> | null;
}

export interface DeployedStrategy {
  id: string | number;
  experiment_id: string | number | null;
  strategy: S;
  instrument: S;
  timeframe: S;
  stage: S;
  weight: N;
  live_trades: N;
  live_pnl_eur: N;
  shadow_trades: N;
  shadow_pnl_eur: N;
  expected_trade_pct: N;
  note: S;
  updated_at: S;
}

export interface Agent {
  id: string | number;
  name: S;
  role: S;
  status: S;
  last_run: S;
  activity: S;
  errors: N;
  last_error: S;
}

export interface Signal {
  ts: S;
  agent: S;
  instrument: S;
  direction: S;
  confidence: N;
  summary: S;
}

export interface Decision {
  ts: S;
  instrument: S;
  side: S;
  strategy: S;
  approved: boolean | null;
  reason: S;
  notional_eur: N;
}

export interface Incident {
  ts: S;
  severity: S;
  component: S;
  message: S;
  recovered: boolean | null;
}

export interface NewsItem {
  ts: S;
  instrument: S;
  title: S;
  publisher: S;
  url: S;
  sentiment: N;
}

export interface ElitePrinciple {
  trader: S;
  principle: S;
  families: string[] | null;
  source: S;
}

export interface EliteFiling {
  institution: S;
  form: S;
  report_date: S;
  filing_date: S;
  url: S;
  freshness_days: N;
}

export interface EliteHolding {
  institution: S;
  issuer: S;
  value_usd: N;
  shares: N;
  report_date: S;
  filing_date: S;
  source: S;
  freshness_days: N;
  confidence: S;
}

export interface Elite {
  principles?: ElitePrinciple[] | null;
  filings?: EliteFiling[] | null;
  holdings?: EliteHolding[] | null;
}

export interface Health {
  ok?: boolean | null;
  mode?: S;
  version?: S;
}

export interface ControlResponse {
  ok: boolean;
  message: string;
}

export type ControlAction =
  | 'start'
  | 'pause'
  | 'resume'
  | 'stop'
  | 'emergency_stop'
  | 'run_experiments'
  | 'reset';

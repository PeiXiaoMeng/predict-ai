/* ────────────────────────────────────────
   与后端 schema 对齐的 TypeScript 类型
   ──────────────────────────────────────── */

// ── Request ──

export interface AnalyzeRequest {
  product_name: string
  product_description: string
  target_users: string[]
  budget_monthly: number
  hypothesis: Record<string, unknown>
}

// ── Competitor Research ──

export interface Competitor {
  name: string
  segment: 'direct' | 'adjacent' | 'substitute'
  pricing: string
  core_features: string[]
  differentiators: string[]
  evidence: string[]
}

export interface MapPoint {
  name: string
  x: number
  y: number
}

export interface CompetitorMap {
  x_axis: string
  y_axis: string
  points: MapPoint[]
}

export interface CompetitorResearch {
  segments: string[]
  competitors: Competitor[]
  competitor_map: CompetitorMap
}

// ── Market Judgement ──

export interface ScoreItem {
  score: number
  confidence: number
  reason: string
}

export interface SignalBreakdown {
  signal: 'search' | 'traffic' | 'content' | 'sentiment'
  value: number
  weight: number
}

export interface MarketJudgement {
  track_heat: ScoreItem
  demand_strength: ScoreItem
  competition_crowdedness: ScoreItem
  signal_breakdown: SignalBreakdown[]
}

// ── ROI Estimation ──

export interface Scenario {
  cac: number
  retention_m3: number
  paid_conversion: number
  arppu: number
  payback_period_months: number
}

export interface StopLossRule {
  window_days: number
  kpi: string
  threshold: string
  action: string
}

export interface ROIEstimation {
  scenarios: {
    conservative: Scenario
    base: Scenario
    aggressive: Scenario
  }
  recommendation: 'go' | 'wait' | 'no-go'
  stop_loss_rule: StopLossRule
}

// ── Strategy Advice ──

export interface RoadmapPhase {
  phase: string
  goal: string
  deliverables: string[]
  metric: string
}

export interface StrategyAdvice {
  launch_strategy: string
  mvp_do: string[]
  mvp_not_do: string[]
  roadmap: RoadmapPhase[]
}

// ── Full Response ──

export interface AnalyzeMeta {
  project_name: string
  analysis_time: string
  confidence: number
}

export interface AnalyzeResponse {
  meta: AnalyzeMeta
  competitor_research: CompetitorResearch
  market_judgement: MarketJudgement
  roi_estimation: ROIEstimation
  strategy_advice: StrategyAdvice
}

// ── Agent Status (UI only) ──

export type AgentName = 'competitor' | 'market' | 'roi' | 'strategy'
export type AgentState = 'idle' | 'running' | 'done' | 'error'

export interface AgentStatusItem {
  name: AgentName
  label: string
  state: AgentState
}

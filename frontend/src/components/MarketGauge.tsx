import type { MarketJudgement } from '../types'

interface GaugeProps {
  label: string
  score: number
  confidence: number
  reason: string
}

function Gauge({ label, score, confidence, reason }: GaugeProps) {
  const color = score >= 75 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444'
  const pct = Math.min(score, 100)

  return (
    <div className="bg-gray-50 rounded-xl p-4">
      <div className="flex justify-between items-baseline mb-2">
        <span className="font-medium text-sm">{label}</span>
        <span className="text-2xl font-bold" style={{ color }}>{score}</span>
      </div>
      {/* 进度条 */}
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden mb-2">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="text-xs text-gray-500 flex justify-between">
        <span>置信度 {(confidence * 100).toFixed(0)}%</span>
        <span>{reason}</span>
      </div>
    </div>
  )
}

interface Props {
  data: MarketJudgement
}

export default function MarketGauge({ data }: Props) {
  const gauges: GaugeProps[] = [
    { label: '🔥 赛道热度', ...data.track_heat },
    { label: '💡 需求强度', ...data.demand_strength },
    { label: '🏟️ 竞争拥挤度', ...data.competition_crowdedness },
  ]

  return (
    <div className="bg-white rounded-2xl shadow-sm border p-5">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <span className="text-2xl">📈</span> 市场判断
      </h2>
      <div className="grid gap-3">
        {gauges.map(g => <Gauge key={g.label} {...g} />)}
      </div>

      {/* 信号明细 */}
      <div className="mt-4">
        <h3 className="text-sm font-medium mb-2 text-gray-500">信号拆解</h3>
        <div className="grid grid-cols-4 gap-2 text-center text-sm">
          {data.signal_breakdown.map(s => (
            <div key={s.signal} className="bg-gray-50 rounded-lg py-2">
              <div className="font-bold text-lg">{typeof s.value === 'number' ? s.value.toFixed(0) : s.value}</div>
              <div className="text-xs text-gray-400">{s.signal}</div>
              <div className="text-xs text-gray-300">权重 {(s.weight * 100).toFixed(0)}%</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

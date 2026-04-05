import type { StrategyAdvice } from '../types'

interface Props {
  data: StrategyAdvice
}

export default function StrategyRoadmap({ data }: Props) {
  const phaseColor: Record<string, string> = {
    P0: 'border-indigo-500 bg-indigo-50',
    P1: 'border-blue-500 bg-blue-50',
    P2: 'border-teal-500 bg-teal-50',
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm border p-5">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <span className="text-2xl">🎯</span> 策略建议
      </h2>

      {/* 上线策略 */}
      <div className="bg-brand-50 rounded-xl p-4 mb-4 text-sm">
        <span className="font-semibold text-brand-700">上线策略：</span>
        {data.launch_strategy}
      </div>

      {/* MVP 做/不做 */}
      <div className="grid grid-cols-2 gap-4 mb-5">
        <div>
          <h3 className="text-sm font-semibold text-green-700 mb-2">✅ MVP 该做</h3>
          <ul className="space-y-1 text-sm">
            {data.mvp_do.map((item, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-green-500 mt-0.5">●</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-red-700 mb-2">❌ MVP 不该做</h3>
          <ul className="space-y-1 text-sm">
            {data.mvp_not_do.map((item, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-red-400 mt-0.5">●</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* 路线图 */}
      <h3 className="text-sm font-semibold text-gray-600 mb-3">🗺️ 路线图</h3>
      <div className="space-y-3">
        {data.roadmap.map((phase, i) => (
          <div
            key={i}
            className={`border-l-4 rounded-lg p-4 ${phaseColor[phase.phase] ?? 'border-gray-300 bg-gray-50'}`}
          >
            <div className="flex items-center gap-3 mb-1">
              <span className="font-bold text-sm">{phase.phase}</span>
              <span className="text-sm font-medium">{phase.goal}</span>
              <span className="ml-auto text-xs bg-white/60 px-2 py-0.5 rounded-full">
                📏 {phase.metric}
              </span>
            </div>
            <div className="text-xs text-gray-600">
              交付物：{phase.deliverables.join(' · ')}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

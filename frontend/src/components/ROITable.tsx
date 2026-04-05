import type { ROIEstimation } from '../types'

const recStyle: Record<string, { bg: string; text: string; label: string }> = {
  go: { bg: 'bg-green-100', text: 'text-green-700', label: '✅ Go' },
  wait: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: '⏳ Wait' },
  'no-go': { bg: 'bg-red-100', text: 'text-red-700', label: '🚫 No-Go' },
}

interface Props {
  data: ROIEstimation
}

export default function ROITable({ data }: Props) {
  const rec = recStyle[data.recommendation] ?? recStyle['wait']
  const tiers = [
    { key: 'conservative' as const, label: '保守', emoji: '🐢' },
    { key: 'base' as const, label: '基准', emoji: '⚖️' },
    { key: 'aggressive' as const, label: '激进', emoji: '🚀' },
  ]

  return (
    <div className="bg-white rounded-2xl shadow-sm border p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <span className="text-2xl">💰</span> ROI 估算
        </h2>
        <span className={`px-3 py-1 rounded-full font-semibold text-sm ${rec.bg} ${rec.text}`}>
          {rec.label}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="py-2 pr-4">情景</th>
              <th className="py-2 pr-4">CAC</th>
              <th className="py-2 pr-4">3月留存</th>
              <th className="py-2 pr-4">付费率</th>
              <th className="py-2 pr-4">ARPPU</th>
              <th className="py-2">回本(月)</th>
            </tr>
          </thead>
          <tbody>
            {tiers.map(({ key, label, emoji }) => {
              const s = data.scenarios[key]
              const pbColor = s.payback_period_months <= 9 ? 'text-green-600' :
                              s.payback_period_months <= 15 ? 'text-yellow-600' : 'text-red-600'
              return (
                <tr key={key} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-medium">{emoji} {label}</td>
                  <td className="py-2 pr-4">¥{s.cac}</td>
                  <td className="py-2 pr-4">{(s.retention_m3 * 100).toFixed(0)}%</td>
                  <td className="py-2 pr-4">{(s.paid_conversion * 100).toFixed(1)}%</td>
                  <td className="py-2 pr-4">¥{s.arppu}</td>
                  <td className={`py-2 font-bold ${pbColor}`}>
                    {s.payback_period_months >= 999 ? '∞' : `${s.payback_period_months} 月`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* 止损线 */}
      <div className="mt-4 bg-red-50 rounded-xl p-4 text-sm">
        <h3 className="font-semibold text-red-700 mb-1">⚠️ 止损线</h3>
        <p className="text-red-600">
          <strong>{data.stop_loss_rule.window_days} 天</strong>内，若{' '}
          <code className="bg-red-100 px-1 rounded">{data.stop_loss_rule.threshold}</code>
          ，则 <em>{data.stop_loss_rule.action}</em>
        </p>
      </div>
    </div>
  )
}

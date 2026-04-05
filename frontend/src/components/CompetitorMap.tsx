import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { CompetitorResearch } from '../types'

const COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6']

interface Props {
  data: CompetitorResearch
}

function toZhAxisName(raw: string) {
  const key = (raw || '').toLowerCase()
  if (key === 'user_value') return '用户价值'
  if (key === 'implementation_complexity' || key === 'implementation_com') return '实现复杂度'
  return raw
}

export default function CompetitorMapChart({ data }: Props) {
  const points = data.competitor_map.points.map((p, i) => ({
    ...p,
    fill: COLORS[i % COLORS.length],
  }))
  const xAxisLabel = toZhAxisName(data.competitor_map.x_axis)
  const yAxisLabel = toZhAxisName(data.competitor_map.y_axis)

  return (
    <div className="bg-white rounded-2xl shadow-sm border p-5">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <span className="text-2xl">🗺️</span> 竞品地图
      </h2>

      {/* 图表 */}
      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" dataKey="x" name={xAxisLabel} domain={[0, 100]}
            label={{ value: xAxisLabel, position: 'insideBottom', offset: -10 }} />
          <YAxis type="number" dataKey="y" name={yAxisLabel} domain={[0, 100]}
            label={{ value: yAxisLabel, angle: -90, position: 'insideLeft' }} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }}
            formatter={(value: unknown, name: string) => [String(value), name]}
            labelFormatter={() => ''} />
          <Scatter data={points}>
            {points.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} r={7} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>

      {/* 图例 */}
      <div className="flex flex-wrap gap-3 mt-3 text-sm">
        {points.map((p, i) => (
          <span key={i} className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
            {p.name}
          </span>
        ))}
      </div>

      {/* 竞品表格 */}
      <div className="mt-5 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="py-2 pr-4">竞品</th>
              <th className="py-2 pr-4">分类</th>
              <th className="py-2 pr-4">定价</th>
              <th className="py-2 pr-4">核心功能</th>
              <th className="py-2">差异点</th>
            </tr>
          </thead>
          <tbody>
            {data.competitors.map((c, i) => (
              <tr key={i} className="border-b last:border-0">
                <td className="py-2 pr-4 font-medium">{c.name}</td>
                <td className="py-2 pr-4">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${
                    c.segment === 'direct' ? 'bg-red-50 text-red-600' :
                    c.segment === 'adjacent' ? 'bg-yellow-50 text-yellow-600' :
                    'bg-blue-50 text-blue-600'
                  }`}>{c.segment}</span>
                </td>
                <td className="py-2 pr-4">{c.pricing}</td>
                <td className="py-2 pr-4">{c.core_features.join(', ')}</td>
                <td className="py-2">{c.differentiators.join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

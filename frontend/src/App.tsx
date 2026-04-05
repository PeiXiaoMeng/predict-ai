import { useState, useCallback } from 'react'
import type { AnalyzeRequest, AnalyzeResponse, AgentStatusItem } from './types'
import { runAnalysis, exportReport, downloadBlob } from './api/client'
import InputForm from './components/InputForm'
import AgentStatus from './components/AgentStatus'
import CompetitorMapChart from './components/CompetitorMap'
import MarketGauge from './components/MarketGauge'
import ROITable from './components/ROITable'
import StrategyRoadmap from './components/StrategyRoadmap'

const INITIAL_AGENTS: AgentStatusItem[] = [
  { name: 'competitor', label: '竞品研究', state: 'idle' },
  { name: 'market', label: '市场判断', state: 'idle' },
  { name: 'roi', label: 'ROI 估算', state: 'idle' },
  { name: 'strategy', label: '策略建议', state: 'idle' },
]

export default function App() {
  const [agents, setAgents] = useState<AgentStatusItem[]>(INITIAL_AGENTS)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = useCallback(async (req: AnalyzeRequest) => {
    setLoading(true)
    setError('')
    setResult(null)

    // 模拟 Agent 逐步执行的 UI 效果
    const names: AgentStatusItem['name'][] = ['competitor', 'market', 'roi', 'strategy']
    setAgents(prev => prev.map(a => ({ ...a, state: 'idle' as const })))

    for (const name of names) {
      setAgents(prev => prev.map(a => a.name === name ? { ...a, state: 'running' } : a))
      await new Promise(r => setTimeout(r, 400)) // 模拟延迟
    }

    try {
      const data = await runAnalysis(req)
      setResult(data)
      setAgents(prev => prev.map(a => ({ ...a, state: 'done' as const })))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '分析失败，请确认后端已启动'
      setError(msg)
      setAgents(prev => prev.map(a => ({ ...a, state: 'error' as const })))
    } finally {
      setLoading(false)
    }
  }, [])

  const handleExport = useCallback(async (format: 'markdown' | 'json') => {
    if (!result) return
    try {
      const blob = await exportReport(result, format)
      const ext = format === 'markdown' ? 'md' : 'json'
      downloadBlob(blob, `report-${result.meta.project_name}.${ext}`)
    } catch {
      setError('导出失败')
    }
  }, [result])

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Header */}
      <header className="text-center mb-8">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-brand-600 to-purple-600 bg-clip-text text-transparent">
          🔮 产品前景分析器
        </h1>
        <p className="text-gray-500 mt-2">输入任意产品描述 → 竞品研究 → 市场判断 → ROI 估算 → 策略建议</p>
      </header>

      {/* 输入 + Agent状态 */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <InputForm onSubmit={handleSubmit} loading={loading} />
        <AgentStatus agents={agents} />
      </div>

      {/* 错误 */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 mb-6">
          ❌ {error}
        </div>
      )}

      {/* 结果面板 */}
      {result && (
        <div className="space-y-6">
          {/* Meta */}
          <div className="bg-white rounded-2xl shadow-sm border p-5 flex items-center justify-between">
            <div>
              <span className="text-sm text-gray-500">项目：</span>
              <span className="font-semibold">{result.meta.project_name}</span>
              <span className="ml-4 text-sm text-gray-500">置信度：</span>
              <span className="font-semibold">{(result.meta.confidence * 100).toFixed(0)}%</span>
              <span className="ml-4 text-sm text-gray-400">{result.meta.analysis_time}</span>
            </div>
            <div className="flex gap-2">
              <button onClick={() => handleExport('markdown')}
                className="px-3 py-1.5 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition">
                📥 导出 Markdown
              </button>
              <button onClick={() => handleExport('json')}
                className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 transition">
                📋 导出 JSON
              </button>
            </div>
          </div>

          {/* 四大模块 */}
          <CompetitorMapChart data={result.competitor_research} />
          <MarketGauge data={result.market_judgement} />
          <ROITable data={result.roi_estimation} />
          <StrategyRoadmap data={result.strategy_advice} />
        </div>
      )}

      {/* Footer */}
      <footer className="text-center text-xs text-gray-400 mt-12 pb-4">
        产品前景分析器 v0.3 — 仅供决策参考
      </footer>
    </div>
  )
}

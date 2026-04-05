import { useState } from 'react'
import type { AnalyzeRequest } from '../types'

interface Props {
  onSubmit: (req: AnalyzeRequest) => void
  loading: boolean
}

export default function InputForm({ onSubmit, loading }: Props) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [users, setUsers] = useState('')
  const [budget, setBudget] = useState('5000')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      product_name: name.trim(),
      product_description: desc.trim(),
      target_users: users.split(',').map(s => s.trim()).filter(Boolean),
      budget_monthly: Number(budget) || 0,
      hypothesis: {},
    })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border p-6 space-y-5">
      <h2 className="text-lg font-semibold flex items-center gap-2">
        <span className="text-2xl">🚀</span> 产品描述
      </h2>

      <div>
        <label className="block text-sm font-medium mb-1">产品名称</label>
        <input
          required
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="例：智能记账 App / 跨境电商平台 / SaaS 项目管理工具"
          className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-500 focus:outline-none"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">产品描述</label>
        <textarea
          required
          rows={4}
          value={desc}
          onChange={e => setDesc(e.target.value)}
          placeholder="描述产品定位、解决的问题、主要功能…"
          className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-500 focus:outline-none resize-none"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">目标用户（逗号分隔）</label>
          <input
            value={users}
            onChange={e => setUsers(e.target.value)}
            placeholder="独立开发者, 小团队"
            className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">月预算（¥）</label>
          <input
            type="number"
            value={budget}
            onChange={e => setBudget(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-500 focus:outline-none"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-brand-600 hover:bg-brand-700 text-white font-medium rounded-lg py-2.5 transition disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? '分析中…' : '开始分析 →'}
      </button>
    </form>
  )
}

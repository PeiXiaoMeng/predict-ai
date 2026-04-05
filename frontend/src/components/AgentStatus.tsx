import type { AgentStatusItem } from '../types'

const stateStyle: Record<string, string> = {
  idle: 'bg-gray-100 text-gray-400',
  running: 'bg-yellow-50 text-yellow-600 animate-pulse',
  done: 'bg-green-50 text-green-600',
  error: 'bg-red-50 text-red-600',
}

const stateIcon: Record<string, string> = {
  idle: '⏸️',
  running: '⏳',
  done: '✅',
  error: '❌',
}

interface Props {
  agents: AgentStatusItem[]
}

export default function AgentStatus({ agents }: Props) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border p-5">
      <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
        <span className="text-2xl">🤖</span> Agent 执行状态
      </h2>
      <div className="grid grid-cols-2 gap-3">
        {agents.map(a => (
          <div
            key={a.name}
            className={`rounded-xl px-4 py-3 flex items-center gap-3 ${stateStyle[a.state]}`}
          >
            <span className="text-xl">{stateIcon[a.state]}</span>
            <div>
              <div className="font-medium text-sm">{a.label}</div>
              <div className="text-xs opacity-70 capitalize">{a.state}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

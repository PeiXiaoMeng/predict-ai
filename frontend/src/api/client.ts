import axios, { AxiosError } from 'axios'
import type { AnalyzeRequest, AnalyzeResponse } from '../types'

// 开发模式走 Vite proxy（相对路径），生产模式可通过环境变量指定后端地址
const BASE_URL = import.meta.env.VITE_API_BASE ?? ''

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

/** 统一错误提取 */
function extractError(e: unknown): string {
  if (e instanceof AxiosError) {
    if (e.response) return `服务端错误 ${e.response.status}: ${JSON.stringify(e.response.data)}`
    if (e.code === 'ERR_NETWORK') return '无法连接后端服务，请确认后端已启动 (http://127.0.0.1:8000)'
    return e.message
  }
  return e instanceof Error ? e.message : '未知错误'
}

/** 发起全量分析 */
export async function runAnalysis(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  try {
    const { data } = await api.post<AnalyzeResponse>('/v1/analyze', req)
    return data
  } catch (e) {
    throw new Error(extractError(e))
  }
}

/** 导出报告 */
export async function exportReport(
  analysisData: AnalyzeResponse,
  format: 'markdown' | 'json' = 'markdown',
): Promise<Blob> {
  try {
    const { data } = await api.post('/v1/export', { data: analysisData, format }, { responseType: 'blob' })
    return data
  } catch (e) {
    throw new Error(extractError(e))
  }
}

/** 下载 Blob 到本地 */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

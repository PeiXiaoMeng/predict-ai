# AI 产品前景分析器 — 前端

技术栈：React 18 + TypeScript + Vite + TailwindCSS + Recharts

## 快速启动

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:3000`，通过 Vite proxy 将 `/v1/*` 请求转发到后端 `http://localhost:8000`。

## 页面

1. **输入区**：产品名称、描述、目标用户、月预算
2. **Agent 状态**：四个 Agent 执行进度
3. **竞品地图**：散点图 + 竞品表格
4. **市场判断**：三指标仪表盘 + 信号拆解
5. **ROI 估算**：三档对比表 + 止损线
6. **策略建议**：做/不做清单 + 路线图
7. **导出**：一键下载 Markdown / JSON 报告

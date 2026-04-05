# 🔮 Predict App — AI驱动的产品前景分析平台

> **输入任意产品描述，4个AI Agent自动完成竞品研究、市场判断、ROI估算与策略建议。**
>
> 完美适配 SaaS / App / 电商 / 硬件 / 内容产品 —— **不限品类**。

[English](README.md) | [中文](README.zh-CN.md)

---

## 📋 功能概览

| 模块 | 功能 | 输出 |
|------|------|------|
| 🔍 **竞品研究 Agent** | 自动发现相似产品，分类，提炼差异点 | 竞品地图（散点图）+ 对比表 |
| 📈 **市场判断 Agent** | 汇总搜索趋势、流量、内容热度、评论情绪 | 赛道热度 / 需求强度 / 竞争拥挤度 |
| 💰 **ROI 估算 Agent** | 保守 / 基准 / 激进三档财务建模 | 回本周期 + 投入建议 + 止损线 |
| 🎯 **策略建议 Agent** | 上线策略 + MVP 做/不做清单 + 路线图 | 分阶段交付里程碑 |

---

### 📸 截图展示

![产品分析流程 - 输入表单](/static/Screenshot/截图1.png)
*图1：产品分析输入表单*

![竞品地图可视化 - 市场定位](/static/Screenshot/截图2.png)
*图2：竞品地图与市场定位*

![市场评分仪表盘 - 核心指标](/static/Screenshot/截图3.png)
*图3：市场健康度核心指标面板*

![ROI三档对比与策略建议](/static/Screenshot/截图4.png)
*图4：ROI 三档场景与策略建议*

---

### 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          前端                                   │
│            React 18 + TypeScript + Vite + TailwindCSS           │
│                                                                 │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │输入表单  │  │Agent状态   │  │可视化图表│  │导出功能      │  │
│  └────┬─────┘  └────────────┘  └──────────┘  └──────────────┘  │
│       │  POST /v1/analyze                                       │
├───────┼─────────────────────────────────────────────────────────┤
│       │           Vite反向代理 (开发) / Nginx (生产)            │
├───────┼─────────────────────────────────────────────────────────┤
│       ▼                     后端                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    FastAPI (Python)                      │    │
│  │                                                         │    │
│  │  ┌──────────────── 编排器 ────────────────────────┐   │    │
│  │  │                                                  │   │    │
│  │  │  ┌─────────────┐  ┌─────────────┐               │   │    │
│  │  │  │  竞品研究    │  │   市场判断   │               │   │    │
│  │  │  │    Agent    │  │   Agent     │ (并行执行)  │   │    │
│  │  │  └──────┬──────┘  └──────┬──────┘               │   │    │
│  │  │         └────────┬───────┘                       │   │    │
│  │  │                  ▼                               │   │    │
│  │  │           ┌────────────┐                         │   │    │
│  │  │           │ ROI估算    │   (依赖市场数据)        │   │    │
│  │  │           └──────┬─────┘                         │   │    │
│  │  │                  ▼                               │   │    │
│  │  │          ┌──────────────┐                        │   │    │
│  │  │          │策略建议Agent  │   (依赖全部上游)       │   │    │
│  │  │          └──────────────┘                        │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                                                         │    │
│  │  ┌──────────────── 工具层 ────────────────────────┐   │    │
│  │  │ 搜索热度 │ 流量 │ 内容热度 │ 评论情绪 │ 竞品   │   │    │
│  │  └─────────────────────────────────────────────────┘   │    │
│  │                                                         │    │
│  │  ┌──────────────── 服务层 ────────────────────────┐   │    │
│  │  │  报告导出 (Markdown / JSON)                      │   │    │
│  │  └─────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

### 📂 目录结构

```
predict-app/
├── .env                           # 运行时环境变量（API Key 等）
├── .env.example                   # 环境变量模板
├── README.md                      # 英文文档
├── README.zh-CN.md                # 中文文档（本文件）
├── docs/
│   └── architecture.md            # 完整架构与 ROI 公式
├── static/
│   └── Screenshot/
│       ├── 截图1.png
│       ├── 截图2.png
│       ├── 截图3.png
│       └── 截图4.png
├── backend/
│   ├── requirements.txt           # Python 依赖
│   └── app/
│       ├── __init__.py
│       ├── main.py                # FastAPI 入口
│       ├── orchestrator.py        # Agent 编排流程
│       ├── schemas.py             # 请求/响应 Schema
│       ├── api_log.py             # API 调用日志工具
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── prompts.py         # Prompt 模板
│       │   └── workflow.py        # Agent 执行逻辑
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── debug.py           # Debug 路由
│       │   └── _debug_ui.html     # Debug UI 页面
│       ├── services/
│       │   ├── __init__.py
│       │   └── report_exporter.py # Markdown/JSON 导出服务
│       └── tools/
│           ├── __init__.py
│           ├── base.py
│           ├── search_trends.py
│           ├── traffic.py
│           ├── content_heat.py
│           ├── review_sentiment.py
│           └── competitor_snapshot.py
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── public/
│   │   └── vite.svg
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css
│       ├── api/
│       │   └── client.ts
│       ├── types/
│       │   └── index.ts
│       └── components/
│           ├── InputForm.tsx
│           ├── AgentStatus.tsx
│           ├── CompetitorMap.tsx
│           ├── MarketGauge.tsx
│           ├── ROITable.tsx
│           └── StrategyRoadmap.tsx
└── .venv/                         # 本地 Python 虚拟环境
```

---

### 🛠️ 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **前端** | React + TypeScript + Vite | 18.x / 5.6 / 6.x |
| | TailwindCSS + Recharts | 3.4 / 2.x |
| **后端** | FastAPI + Pydantic | 0.115 / v2.9 |
| | Python + Uvicorn | 3.10+ / 0.30 |
| **数据** | 5个可插拔工具 | 真实/Mock混合 |

---

### 🚀 快速启动

#### 后端启动

```bash
cd predict-app
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

**访问端点：**
- http://127.0.0.1:8000/health → 健康检查
- http://127.0.0.1:8000/docs → Swagger API文档
- http://127.0.0.1:8000/debug/ui → 实时API日志

#### 前端启动

```bash
cd frontend
npm install
npm run dev
```

**访问地址：** http://localhost:3000

---

### 📡 API调用示例

**请求：**
```json
POST /v1/analyze
{
  "product_name": "智能记账App",
  "product_description": "为年轻上班族提供的自动记账工具，通过银行API自动分类消费",
  "target_users": ["年轻上班族"],
  "budget_monthly": 8000
}
```

**响应：**
```json
{
  "meta": { "project_name": "...", "confidence": 0.85 },
  "competitor_research": { "competitors": [...], "competitor_map": {...} },
  "market_judgement": { "track_heat": 78, "demand_strength": 62, ... },
  "roi_estimation": { "scenarios": {...}, "recommendation": "GO" },
  "strategy_advice": { "launch_strategy": "...", "mvp_do": [...], ... }
}
```

---

### 📊 ROI公式

**单用户月毛利：**

$$GM_t = p \times ARPPU \times r_t - c \times r_t$$

**生命周期价值（3年周期）：**

$$LTV_n = \sum_{t=1}^{n} \frac{GM_t}{(1+i)^t}$$

**做/不做决策：**
- ✅ **应该做** 如果基准回本 ≤ 9个月 且 保守回本 ≤ 15个月
- ⏳ **等等看** 如果基准 9-15个月 且存在优化杠杆
- 🚫 **不应该做** 如果基准 > 15个月 或 保守永远无法回本

---

### 🔌 数据工具（可插拔）

| 工具 | 状态 | 数据源 |
|------|------|--------|
| `search_trends` | 🟡 Mock | Google Trends / SerpAPI |
| `traffic_estimation` | 🟢 真实 | DataForSEO SimilarWeb API |
| `content_heat` | 🟢 真实 | YouTube Data API + Reddit API |
| `review_sentiment` | 🟢 真实 | App Store + Google Play + Reddit |
| `competitor_snapshot` | 🟡 Mock | ProductHunt API |

---

### 📄 开源协议

MIT

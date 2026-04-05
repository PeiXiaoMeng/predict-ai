# AI 产品前景分析器架构设计（v1）

## 1. 总体目标

输入一段产品描述，系统自动完成：
- 竞品研究（找相似产品 + 分类 + 差异点）
- 市场判断（热度/需求/拥挤度）
- ROI 估算（三档模型）
- 策略建议（上线策略 + MVP 路线）

输出一个可执行的立项决策包。

---

## 2. 多 Agent 流程

### 2.1 流程图（文本）

1. `Orchestrator`
   - 接收用户输入
   - 标准化输入与假设
2. `CompetitorResearchAgent`
   - 调搜索工具，找竞品
   - 做竞品分类与差异提炼
   - 产出竞品地图
3. `MarketJudgementAgent`
   - 汇总搜索趋势、流量、内容热度、评论情绪
   - 计算赛道热度、需求强度、拥挤度
4. `ROIEstimationAgent`
   - 基于假设做保守/基准/激进三档
   - 输出 CAC、留存、付费率、回本周期
5. `StrategyAdvisorAgent`
   - 结合上面 3 个 Agent 输出
   - 给出上线策略、MVP 做/不做清单、止损线
6. `ReportComposer`
   - 聚合为统一 schema

### 2.2 编排建议

- 执行顺序：
  - 先并行：竞品研究、市场判断
  - 后串行：ROI（依赖市场判断）
  - 最后策略建议（依赖全部上游）
- 失败降级：
  - 某工具不可用时，标记 `confidence` 降低并给出替代数据来源建议

---

## 3. Agent Prompt 设计

> 采用统一模板：`System + Task + Constraints + Output Schema + Self-Check`

### 3.1 竞品研究 Agent Prompt

**System**
- 你是资深产品研究分析师，擅长竞品定位、功能拆解与差异化洞察。

**Task**
- 根据用户产品描述，识别同赛道与替代赛道的产品。
- 输出：产品分类、核心功能对比、差异点、竞品地图坐标（价值/复杂度）。

**Constraints**
- 至少覆盖 8 个竞品，且包含 2 个跨赛道替代方案。
- 每个差异点必须可追溯到证据摘要。

**Output Schema（简化）**
- `competitors[]`
- `segments[]`
- `differentiators[]`
- `competitor_map.points[]`

**Self-Check**
- 是否覆盖头部、中腰部、新兴产品？
- 是否存在同质化误判？

### 3.2 市场判断 Agent Prompt

**System**
- 你是市场情报分析师，擅长把异构信号转换成可比较指标。

**Task**
- 汇总搜索趋势、流量、内容热度与评论情绪，评估：
  - 赛道热度
  - 用户需求强度
  - 竞争拥挤度

**Constraints**
- 所有结论必须给 0-100 分与置信度。
- 说明噪声来源与样本偏差。

**Output Schema（简化）**
- `track_heat`
- `demand_strength`
- `competition_crowdedness`
- `signal_breakdown[]`

**Self-Check**
- 是否有短期热点误导长期趋势？
- 情绪样本是否偏向吐槽场景？

### 3.3 ROI 估算 Agent Prompt

**System**
- 你是增长与财务建模分析师，输出可执行且可止损的模型。

**Task**
- 基于输入假设计算保守/基准/激进三档：
  - 获客成本 CAC
  - 留存
  - 付费率
  - 回本周期
- 给出投入建议与止损线。

**Constraints**
- 所有参数必须可解释（来源、范围、敏感度）。
- 标注影响 ROI 的 Top 3 杠杆。

**Output Schema（简化）**
- `scenarios.conservative/base/aggressive`
- `payback_period_months`
- `recommendation`
- `stop_loss_rule`

**Self-Check**
- 参数是否出现互相矛盾（高 CAC + 低 ARPU 仍高回报）？

### 3.4 策略建议 Agent Prompt

**System**
- 你是 0-1 产品策略负责人，强调“可上线、可验证、可止损”。

**Task**
- 输出上线策略、MVP 做/不做清单、分阶段路线图。

**Constraints**
- 只给能在 6-8 周内验证的动作。
- 每条建议绑定目标指标与观察窗口。

**Output Schema（简化）**
- `launch_strategy`
- `mvp_do[]`
- `mvp_not_do[]`
- `milestones[]`

**Self-Check**
- 是否避免“功能堆叠”而缺乏单点价值验证？

---

## 4. 工具接口设计（Tool Contracts）

> 以“可替换的数据连接器”设计，先定义抽象接口，后接具体供应商 API。

### 4.1 Search Trends Tool
- 输入：`keywords[]`, `region`, `time_range`
- 输出：`trend_index`, `related_queries[]`, `seasonality`

### 4.2 Traffic Estimation Tool
- 输入：`domains[]`, `region`
- 输出：`monthly_visits`, `traffic_sources`, `engagement`

### 4.3 Content Heat Tool
- 输入：`topics[]`, `platforms[]`, `time_range`
- 输出：`post_volume`, `interaction_rate`, `creator_count`

### 4.4 Review Sentiment Tool
- 输入：`product_names[]`, `channels[]`
- 输出：`sentiment_score`, `pain_points[]`, `feature_requests[]`

### 4.5 Competitor Snapshot Tool
- 输入：`product_name`
- 输出：`pricing`, `core_features[]`, `target_user`, `positioning`

---

## 5. 统一输出 Schema（建议 JSON）

```json
{
  "meta": {
    "project_name": "string",
    "analysis_time": "ISO-8601",
    "confidence": 0.0
  },
  "competitor_research": {
    "segments": ["direct", "adjacent", "substitute"],
    "competitors": [
      {
        "name": "string",
        "segment": "direct",
        "pricing": "string",
        "core_features": ["string"],
        "differentiators": ["string"],
        "evidence": ["string"]
      }
    ],
    "competitor_map": {
      "x_axis": "user_value",
      "y_axis": "implementation_complexity",
      "points": [
        {"name": "string", "x": 0, "y": 0}
      ]
    }
  },
  "market_judgement": {
    "track_heat": {"score": 0, "confidence": 0.0, "reason": "string"},
    "demand_strength": {"score": 0, "confidence": 0.0, "reason": "string"},
    "competition_crowdedness": {"score": 0, "confidence": 0.0, "reason": "string"},
    "signal_breakdown": [
      {"signal": "search|traffic|content|sentiment", "value": 0.0, "weight": 0.0}
    ]
  },
  "roi_estimation": {
    "scenarios": {
      "conservative": {
        "cac": 0,
        "retention_m3": 0.0,
        "paid_conversion": 0.0,
        "arppu": 0,
        "payback_period_months": 0
      },
      "base": {},
      "aggressive": {}
    },
    "recommendation": "go|wait|no-go",
    "stop_loss_rule": {
      "window_days": 0,
      "kpi": "string",
      "threshold": "string",
      "action": "string"
    }
  },
  "strategy_advice": {
    "launch_strategy": "string",
    "mvp_do": ["string"],
    "mvp_not_do": ["string"],
    "roadmap": [
      {"phase": "P0|P1|P2", "goal": "string", "deliverables": ["string"], "metric": "string"}
    ]
  }
}
```

---

## 6. ROI 核心公式（v1）

设：
- $CAC$：单个付费用户获客成本
- $r_t$：第 $t$ 月留存率
- $p$：付费转化率
- $ARPPU$：付费用户月均收入
- $c$：单位用户月服务成本

### 6.1 单用户月毛利

$$
GM_t = p \cdot ARPPU \cdot r_t - c \cdot r_t
$$

### 6.2 LTV（离散近似）

$$
LTV_n = \sum_{t=1}^{n} \frac{GM_t}{(1+i)^t}
$$

其中 $i$ 为贴现率（月）。

### 6.3 回本周期（Payback Period）

找到最小 $k$，使：

$$
\sum_{t=1}^{k} \frac{GM_t}{(1+i)^t} \ge CAC
$$

则 $k$ 为回本月数。

### 6.4 投入建议规则（示例）

- `Go`：基准情景 $k \le 9$ 月 且 保守情景 $k \le 15$ 月
- `Wait`：基准情景 $9 < k \le 15$ 月，且存在可优化杠杆
- `No-Go`：基准情景 $k > 15$ 月，或保守情景长期无法回本

### 6.5 止损线（示例）

- 观察窗口：前 60 天
- 条件：若 `激活率 < 20%` 且 `7日留存 < 15%` 且 `内容自然流量占比 < 30%`
- 动作：停止新增投放，仅保留低成本实验

---

## 7. 后端模块建议（Python）

- `app/main.py`：FastAPI 入口
- `app/schemas.py`：请求/响应模型
- `app/orchestrator.py`：Agent 编排
- `app/agents/*.py`：四类 Agent
- `app/tools/*.py`：外部工具适配器
- `app/evaluator/*.py`：评分与 ROI 计算器

---

## 8. 前端展示建议

- 输入区：产品描述、目标用户、预算、周期
- Agent 状态区：正在执行/完成/置信度
- 可视化区：
  - 竞品地图散点图
  - 市场三指标仪表盘
  - ROI 三档对比表
  - MVP 路线图甘特条

---

## 9. v1 到 v2 演进

- v1：规则 + LLM 推理 + 外部工具 API
- v2：引入历史项目库做参数先验（行业基线）
- v3：A/B 数据回流，自动校准 ROI 参数

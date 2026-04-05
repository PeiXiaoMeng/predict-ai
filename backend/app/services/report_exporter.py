"""报告导出服务 —— Markdown + 简易 HTML-to-PDF"""
from __future__ import annotations

import json
from typing import Any


def _score_emoji(score: int) -> str:
    if score >= 75:
        return "🟢"
    elif score >= 50:
        return "🟡"
    return "🔴"


def _rec_label(rec: str) -> str:
    return {"go": "✅ Go", "wait": "⏳ Wait", "no-go": "🚫 No-Go"}.get(rec, rec)


def export_markdown(data: dict[str, Any]) -> str:
    meta = data.get("meta", {})
    cr = data.get("competitor_research", {})
    mj = data.get("market_judgement", {})
    roi = data.get("roi_estimation", {})
    sa = data.get("strategy_advice", {})

    lines: list[str] = []

    # ── Header ──
    lines.append(f"# 📊 产品前景分析报告：{meta.get('project_name', '-')}")
    lines.append("")
    lines.append(f"> 生成时间：{meta.get('analysis_time', '-')}  ")
    lines.append(f"> 总体置信度：**{meta.get('confidence', '-')}**")
    lines.append("")

    # ── 1. 竞品研究 ──
    lines.append("## 1️⃣ 竞品研究")
    lines.append("")
    lines.append(f"赛道分类：{', '.join(cr.get('segments', []))}")
    lines.append("")
    competitors = cr.get("competitors", [])
    if competitors:
        lines.append("| 竞品 | 分类 | 定价 | 核心功能 | 差异点 |")
        lines.append("|------|------|------|----------|--------|")
        for c in competitors:
            features = ", ".join(c.get("core_features", []))
            diffs = ", ".join(c.get("differentiators", []))
            lines.append(f"| {c['name']} | {c.get('segment','-')} | {c.get('pricing','-')} | {features} | {diffs} |")
    lines.append("")

    cmap = cr.get("competitor_map", {})
    if cmap.get("points"):
        lines.append("### 竞品地图")
        lines.append(f"- X 轴：{cmap.get('x_axis','')}")
        lines.append(f"- Y 轴：{cmap.get('y_axis','')}")
        lines.append("")
        for p in cmap["points"]:
            lines.append(f"  - **{p['name']}** ({p['x']}, {p['y']})")
    lines.append("")

    # ── 2. 市场判断 ──
    lines.append("## 2️⃣ 市场判断")
    lines.append("")
    for key, label in [("track_heat", "赛道热度"), ("demand_strength", "需求强度"), ("competition_crowdedness", "竞争拥挤度")]:
        item = mj.get(key, {})
        sc = item.get("score", 0)
        lines.append(f"- {_score_emoji(sc)} **{label}**：{sc}/100（置信 {item.get('confidence','-')}）— {item.get('reason','')}")
    lines.append("")

    signals = mj.get("signal_breakdown", [])
    if signals:
        lines.append("| 信号 | 值 | 权重 |")
        lines.append("|------|----|------|")
        for s in signals:
            lines.append(f"| {s['signal']} | {s['value']} | {s['weight']} |")
    lines.append("")

    # ── 3. ROI 估算 ──
    lines.append("## 3️⃣ ROI 估算")
    lines.append("")
    scenarios = roi.get("scenarios", {})
    if scenarios:
        lines.append("| 情景 | CAC | 3月留存 | 付费率 | ARPPU | 回本(月) |")
        lines.append("|------|-----|---------|--------|-------|----------|")
        for tier, s in scenarios.items():
            lines.append(
                f"| {tier} | ¥{s.get('cac','-')} | {s.get('retention_m3','-')} | {s.get('paid_conversion','-')} | ¥{s.get('arppu','-')} | {s.get('payback_period_months','-')} |"
            )
    lines.append("")
    lines.append(f"**投入建议**：{_rec_label(roi.get('recommendation', '-'))}")
    lines.append("")
    sl = roi.get("stop_loss_rule", {})
    if sl:
        lines.append(f"**止损线**：{sl.get('window_days','')}天内，若 `{sl.get('kpi','')}` {sl.get('threshold','')}，则 {sl.get('action','')}")
    lines.append("")

    # ── 4. 策略建议 ──
    lines.append("## 4️⃣ 策略建议")
    lines.append("")
    lines.append(f"**上线策略**：{sa.get('launch_strategy', '-')}")
    lines.append("")
    lines.append("### ✅ MVP 该做")
    for item in sa.get("mvp_do", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### ❌ MVP 不该做")
    for item in sa.get("mvp_not_do", []):
        lines.append(f"- {item}")
    lines.append("")
    roadmap = sa.get("roadmap", [])
    if roadmap:
        lines.append("### 🗺️ 路线图")
        lines.append("")
        lines.append("| 阶段 | 目标 | 交付物 | 核心指标 |")
        lines.append("|------|------|--------|----------|")
        for r in roadmap:
            deliverables = ", ".join(r.get("deliverables", []))
            lines.append(f"| {r['phase']} | {r['goal']} | {deliverables} | {r['metric']} |")
    lines.append("")

    # ── Footer ──
    lines.append("---")
    lines.append("*本报告由产品前景分析器自动生成，仅供决策参考。*")

    return "\n".join(lines)


def export_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)

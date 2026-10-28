"""Pure, offline helpers for a source-grounded creator research report."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

PROFILE_RE = re.compile(r"^/user/profile/([0-9a-fA-F]{24})/?$")
NOTE_RE = re.compile(r"^/(?:explore|discovery/item)/([0-9a-fA-F]{24})/?$")
TOPICS = {
    "Agent 架构与规划": ("agent", "智能体", "规划", "planning", "plan-and-execute", "react"),
    "工具调用与 MCP": ("mcp", "工具调用", "tool calling", "function calling", "tools"),
    "记忆与上下文": ("memory", "记忆", "上下文", "context", "checkpoint"),
    "RAG 与检索": ("rag", "检索", "向量", "embedding", "rerank"),
    "LangGraph 与工作流": ("langgraph", "langchain", "工作流", "workflow", "stategraph"),
    "Agent Harness 与工程化": ("harness", "评测", "eval", "生产", "监控", "可观测", "部署"),
    "面试与面经": ("面试", "面经", "技术面", "offer", "笔试", "社招", "校招"),
}


def parse_profile_url(raw: str) -> tuple[str, str]:
    """Allow only an explicit Xiaohongshu creator page; no shortlinks or external URLs."""
    parsed = urlparse(raw.strip())
    if parsed.scheme != "https" or parsed.hostname not in ("www.xiaohongshu.com", "xiaohongshu.com"):
        raise ValueError("请粘贴 https://www.xiaohongshu.com/user/profile/... 格式的主页链接")
    match = PROFILE_RE.fullmatch(parsed.path)
    if not match or parsed.username or parsed.password or parsed.port:
        raise ValueError("链接不是有效的小红书博主主页链接")
    creator_id = match.group(1).lower()
    return f"https://www.xiaohongshu.com/user/profile/{creator_id}", creator_id


def canonical_note_url(raw: str) -> str | None:
    parsed = urlparse(urljoin("https://www.xiaohongshu.com", raw))
    if parsed.scheme != "https" or parsed.hostname not in ("www.xiaohongshu.com", "xiaohongshu.com"):
        return None
    match = NOTE_RE.fullmatch(parsed.path)
    if not match:
        return None
    return f"https://www.xiaohongshu.com/explore/{match.group(1).lower()}"


def note_topics(item: dict) -> list[str]:
    source = " ".join(str(item.get(key) or "") for key in ("title", "preview", "body")).lower()
    return [topic for topic, terms in TOPICS.items() if any(term.lower() in source for term in terms)]


def prepare_analysis_input(notes: list[dict], focus: str) -> str:
    records = []
    for item in notes:
        if item.get("status") not in ("text_read", "preview_only"):
            continue
        records.append({
            "id": item["note_id"], "url": item["url"], "title": item.get("title", ""),
            "text": (item.get("body") or item.get("preview") or "")[:2400],
            "status": item["status"], "images_not_transcribed": item.get("images_not_transcribed", True),
        })
    return json.dumps({"focus": focus, "notes": records}, ensure_ascii=False)


def render_evidence_report(profile: str, focus: str, notes: list[dict], discovered: int, stop_reason: str) -> str:
    statuses = Counter(item.get("status", "unknown") for item in notes)
    sections = [
        "# 小红书博主资料阅读报告",
        "",
        f"- 博主主页：{profile}",
        f"- 研究方向：{focus or '所有可访问主题'}",
        f"- 生成时间（UTC）：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        f"- 发现的帖子：{discovered} 篇（仅本次可见范围，不代表博主全部历史帖子）",
        f"- 读取到文本的帖子：{statuses['text_read']} 篇",
        f"- 仅有预览信息：{statuses['preview_only']} 篇",
        f"- 访问失败或受限：{len(notes)-statuses['text_read']-statuses['preview_only']} 篇",
        "",
        "> 本文件是可核查的阅读与主题索引，不等于完整的 AI 观点分析。图片文字与视频尚未转写；任何没有实际读到的内容都不应作为博主观点。",
        "",
    ]
    if stop_reason:
        sections += [f"**本次停止原因：** {stop_reason}", ""]

    themes: dict[str, list[dict]] = {name: [] for name in TOPICS}
    for item in notes:
        for topic in note_topics(item):
            themes[topic].append(item)
    sections += ["## 主题分布（按已读取的文本和预览关键词归类）", ""]
    for topic, items in themes.items():
        if not items:
            continue
        sections.append(f"### {topic}（{len(items)} 篇）")
        sections.append("")
        for item in items[:30]:
            title = (item.get("title") or item["note_id"]).replace("[", "［").replace("]", "］")
            sections.append(f"- [{title}]({item['url']}) — {item.get('status','unknown')}")
        sections.append("")
    if not any(themes.values()):
        sections += ["暂无足够文字构建主题分布。", ""]
    sections += ["## 笔记原文索引", ""]
    for item in notes:
        title = item.get("title") or item["note_id"]
        sections += [
            f"### {title}",
            f"- 来源：{item['url']}",
            f"- 状态：{item.get('status', 'unknown')}",
            f"- 图片文字是否完整：{'否' if item.get('images_not_transcribed', True) else '已处理'}",
            "",
        ]
        body = (item.get("body") or item.get("preview") or "").strip()
        if body:
            sections.extend(["**已读取内容片段：**", "", body[:1600], ""])
    sections += [
        "## 待补充内容",
        "",
        "如果帖子以图片为主，需进一步进行图片文字识别；如果页面提示登录或安全限制，应在授权访问环境内处理，不推断缺失内容。",
        "",
    ]
    return "\n".join(sections)


def write_outputs(directory: Path, profile: str, focus: str, notes: list[dict], discovered: int, stop_reason: str, ai_report: str | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    safe_notes = []
    for item in notes:
        # Navigation tokens are deliberately not persisted.
        safe_notes.append({key: value for key, value in item.items() if key not in ("navigation_url", "xsec_token")})
    with (directory / "notes.jsonl").open("w", encoding="utf-8") as handle:
        for item in safe_notes:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    (directory / "analysis_input.json").write_text(
        prepare_analysis_input(safe_notes, focus), encoding="utf-8"
    )
    (directory / "report.md").write_text(
        render_evidence_report(profile, focus, safe_notes, discovered, stop_reason),
        encoding="utf-8"
    )
    if ai_report:
        (directory / "ai_analysis.md").write_text(ai_report, encoding="utf-8")
    manifest = {
        "profile": profile, "focus": focus, "discovered_in_this_run": discovered,
        "attempted": len(notes),
        "text_read": sum(x.get("status") == "text_read" for x in notes),
        "preview_only": sum(x.get("status") == "preview_only" for x in notes),
        "stop_reason": stop_reason,
        "ai_analysis_created": bool(ai_report),
        "limitation": "Not a complete history; images and videos not transcribed",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

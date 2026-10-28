#!/usr/bin/env python3
"""Filter MediaCrawler creator JSONL into auditable AI Agent interview research inputs."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

INTERVIEW_TERMS = (
    "面试", "面经", "技术面", "拷打", "笔试", "面试官", "offer", "面题",
    "校招", "社招", "秋招", "春招",
)
AGENT_TERMS = (
    "agent", "智能体", "langgraph", "langchain", "multi-agent",
    "multi agent", "mcp", "rag", "工具调用", "function calling",
    "tool calling", "多智能体",
)
AI_TERMS = ("人工智能", "大模型", "llm", "aigc", "ai ")
FIELDS = [
    "note_id", "title", "desc", "time", "type", "note_url",
    "image_list", "video_url", "tag_list", "liked_count",
    "collected_count", "comment_count", "match_level", "match_reason",
]


def classify(note: dict) -> tuple[str, str]:
    title = str(note.get("title") or "").lower()
    text = " ".join(str(note.get(k) or "") for k in ("title", "desc", "tag_list")).lower()
    interview = any(word in text for word in INTERVIEW_TERMS)
    agent = any(word in text for word in AGENT_TERMS)
    ai = any(word in text for word in AI_TERMS)
    if interview and agent:
        return "direct", "面试关键词 + Agent 技术关键词"
    if interview and ai:
        return "review", "面试关键词 + AI 相关关键词，需人工复核"
    if interview:
        return "review", "存在面试关键词，需人工复核是否涉及 Agent"
    if any(word in title for word in ("agent", "智能体", "langgraph", "langchain")):
        return "related", "标题包含 Agent 技术关键词，但未出现面试语义"
    return "other", "未命中"


def load_notes(paths: list[Path]) -> tuple[list[dict], int]:
    found: dict[str, dict] = {}
    invalid_lines = 0
    for path in paths:
        with path.open("r", encoding="utf-8-sig") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    invalid_lines += 1
                    continue
                if not isinstance(data, dict):
                    invalid_lines += 1
                    continue
                note_id = str(data.get("note_id") or "").strip()
                if not note_id:
                    invalid_lines += 1
                    continue
                found[note_id] = data  # latest record wins
    return list(found.values()), invalid_lines


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def process(input_paths: list[Path], output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    notes, invalid = load_notes(input_paths)
    rows = []
    for note in notes:
        level, reason = classify(note)
        row = {key: note.get(key, "") for key in FIELDS}
        row["match_level"] = level
        row["match_reason"] = reason
        rows.append(row)

    candidates = [r for r in rows if r["match_level"] in ("direct", "review")]
    image_queue = [r for r in rows if r["image_list"] and r["match_level"] != "other"]
    write_csv(output_dir / "all_posts.csv", rows)
    write_csv(output_dir / "agent_interview_candidates.csv", candidates)
    write_csv(output_dir / "image_review_queue.csv", image_queue)
    with (output_dir / "analysis_input.jsonl").open("w", encoding="utf-8") as out:
        for row in candidates:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "unique_posts": len(rows),
        "direct_matches": sum(r["match_level"] == "direct" for r in rows),
        "needs_review": sum(r["match_level"] == "review" for r in rows),
        "agent_topic_only": sum(r["match_level"] == "related" for r in rows),
        "image_review_queue": len(image_queue),
        "invalid_or_missing_id_lines": invalid,
        "source_files": [str(p) for p in input_paths],
        "important": "仅搜索标题、描述和标签；图片文字及视频内容需要另行识别。此结果不代表博主全部帖子。",
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, help="Directory containing creator_contents_*.jsonl")
    parser.add_argument("--input-file", type=Path, help="Single MediaCrawler contents JSONL file")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    paths = (
        [args.input_file]
        if args.input_file
        else sorted((args.input_dir or Path("vendor/MediaCrawler/data/xhs/jsonl")).glob("creator_contents_*.jsonl"))
    )
    paths = [p for p in paths if p.is_file()]
    if not paths:
        parser.error("找不到 creator_contents_*.jsonl。请先获取有权使用的原始数据。")
    print(json.dumps(process(paths, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

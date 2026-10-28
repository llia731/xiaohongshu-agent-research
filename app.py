"""Local creator-research UI. Launches a dedicated visible Chrome process."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="小红书博主知识研究", page_icon="📚")
st.title("小红书博主知识研究")
st.caption("输入主页链接，使用本地 Chrome 浏览可访问的帖子，生成带出处的资料报告。")
st.info("首版：最多尝试阅读 50 篇，不识别图片文字和视频；若没有模型 API Key，只生成资料索引。")

with st.form("creator"):
    profile_url = st.text_input("小红书博主主页链接", value="https://www.xiaohongshu.com/user/profile/63572290000000001901d19a")
    focus = st.text_input("研究重点", value="AI Agent 面试、知识体系和核心观点")
    maximum = st.slider("本次最多尝试阅读", min_value=3, max_value=50, value=20)
    available = bool(os.getenv("OPENAI_API_KEY"))
    use_ai = st.checkbox("调用大模型生成知识与观点报告（需单独 API Key）", value=available, disabled=not available)
    start = st.form_submit_button("开始分析", type="primary", use_container_width=True)

if start:
    from scripts.research_core import parse_profile_url
    try:
        parse_profile_url(profile_url)
    except ValueError as exc:
        st.error(str(exc))
    else:
        command = [sys.executable, "-m", "scripts.creator_research",
                   "--profile-url", profile_url, "--focus", focus,
                   "--max-notes", str(maximum),
                   "--output-dir", str(ROOT / "outputs" / "creator_research")]
        if use_ai:
            command.append("--use-ai")
        with st.spinner("正在通过本地 Chrome 阅读。首次需要登录时，请在弹出的 Chrome 内正常扫码。"):
            try:
                result = subprocess.run(command, cwd=str(ROOT), capture_output=True,
                                        encoding="utf-8", errors="replace", timeout=900)
                if result.returncode:
                    st.error("本次运行失败，请查看启动程序的终端输出。")
                    st.code((result.stderr or "")[-1000:])
                else:
                    st.success("本次阅读已结束，请核对实际读取的帖子数量。")
                    st.code((result.stdout or "")[-1000:])
            except subprocess.TimeoutExpired:
                st.error("任务超时。请检查本地 Chrome 的页面状态。")

st.divider()
st.subheader("研究结果")
root = ROOT / "outputs" / "creator_research"
runs = sorted((p for p in root.iterdir() if p.is_dir()), reverse=True) if root.exists() else []
if runs:
    chosen = st.selectbox("本地任务", runs, format_func=lambda p: p.name)
    manifest = chosen / "manifest.json"
    if manifest.is_file():
        st.json(manifest.read_text(encoding="utf-8"))
    ai = chosen / "ai_analysis.md"
    if ai.is_file():
        st.subheader("AI 知识分析")
        st.markdown(ai.read_text(encoding="utf-8"))
        st.download_button("下载 AI 报告", ai.read_bytes(), file_name="ai_analysis.md")
    report = chosen / "report.md"
    if report.is_file():
        st.subheader("原帖与主题索引")
        st.markdown(report.read_text(encoding="utf-8"))
        st.download_button("下载来源报告", report.read_bytes(), file_name="report.md")
    data = chosen / "analysis_input.json"
    if data.is_file():
        st.download_button("下载数据用于 ChatGPT 深入分析", data.read_bytes(), file_name="analysis_input.json")
else:
    st.write("尚无结果。首次使用请先运行一次。")

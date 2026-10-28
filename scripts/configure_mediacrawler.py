#!/usr/bin/env python3
"""Configure a local upstream checkout without committing personal tokens."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

EXPECTED_USER = "63572290000000001901d19a"


def parse_profile_url(value: str) -> str:
    if not value:
        raise ValueError("未提供主页完整 URL。请通过 XHS_PROFILE_URL 设置。")
    url = urlparse(value.strip())
    if url.scheme != "https" or url.hostname not in {"xiaohongshu.com", "www.xiaohongshu.com"}:
        raise ValueError("主页必须使用 https://www.xiaohongshu.com/user/profile/... 格式")
    if url.path.rstrip("/") != f"/user/profile/{EXPECTED_USER}":
        raise ValueError("主页用户 ID 与目标博主不匹配")
    qs = parse_qs(url.query)
    if not qs.get("xsec_token") or not qs.get("xsec_source"):
        raise ValueError("缺少 xsec_token 或 xsec_source；请从浏览器复制最新完整主页 URL")
    return value.strip()


def configure(upstream: Path, profile_url: str, download_media: bool = False) -> None:
    xhs_config = upstream / "config" / "xhs_config.py"
    base_config = upstream / "config" / "base_config.py"
    if not xhs_config.is_file() or not base_config.is_file():
        raise FileNotFoundError("不是完整的 MediaCrawler 仓库目录，找不到 config 文件")
    # Overrides are appended only to an expendable local checkout (vendor/ is gitignored).
    with xhs_config.open("a", encoding="utf-8") as f:
        f.write("\n# Local research configuration (generated)\n")
        f.write(f"XHS_CREATOR_ID_LIST = [{profile_url!r}]\n")
    with base_config.open("a", encoding="utf-8") as f:
        f.write("\n# Local research configuration (generated)\n")
        f.write('CRAWLER_TYPE = "creator"\n')
        f.write('SAVE_DATA_OPTION = "jsonl"\n')
        f.write("CRAWLER_MAX_NOTES_COUNT = 20\n")
        f.write("ENABLE_GET_COMMENTS = False\n")
        f.write("MAX_CONCURRENCY_NUM = 1\n")
        f.write("CRAWLER_MAX_SLEEP_SEC = 3\n")
        f.write(f"ENABLE_GET_MEDIA = {bool(download_media)!r}\n")
        f.write("ENABLE_IP_PROXY = False\n")
        f.write("SAVE_LOGIN_STATE = True\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-dir", type=Path, default=Path("vendor/MediaCrawler"))
    parser.add_argument("--profile-url", default=os.getenv("XHS_PROFILE_URL", ""))
    parser.add_argument("--download-media", action="store_true")
    args = parser.parse_args()
    profile_url = parse_profile_url(args.profile_url)
    configure(args.upstream_dir, profile_url, args.download_media)
    print("配置已写入本地 MediaCrawler 工作目录，未更改研究项目的 Git 跟踪文件。")


if __name__ == "__main__":
    main()

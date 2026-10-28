# 小红书知识博主研究

> **Ubuntu 服务器：** 请先参照 [Linux 环境检查与部署说明](LINUX_SETUP.md) 运行网络与 Chromium 访问测试，再决定是否启动完整网页程序。

> **推荐入口：** 请先阅读 [Windows 一键使用说明](QUICKSTART.md)，运行 start_windows.ps1 后在本地网页粘贴博主主页链接即可开始尝试读取。大模型自动观点报告为可选功能，需要独立配置 API Key。

目标：整理“程序员峰哥”（小红书用户 ID：`63572290000000001901d19a`）在可访问、可合法使用范围内发布的 Agent 面试相关笔记，并建立有原帖出处的研究材料。

> **状态与边界**：仓库中包含真实的 GitHub Actions 自动环境测试，但不包含已验证成功的小红书爬取结果。GitHub 托管运行器没有你本地小红书的登录会话；不能把无人值守登录视作已解决。

## 架构

- [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 用于获取有权访问和使用的帖子；本项目不复制其源代码。
- `scripts/configure_mediacrawler.py`：将指定博主与少量采集配置写入本地克隆的 MediaCrawler。
- `scripts/filter_agent_posts.py`：对上游导出的 `creator_contents_*.jsonl` 去重、筛选和整理。
- `scripts/diagnose_env.py`：只读检查 Python、uv、Node、Chrome 与 DNS。
- `.github/workflows/ci.yml`：每次 push 自动测试筛选流程，并尝试安装固定版本的上游依赖。

固定 MediaCrawler 提交：`68d9ef1c1da22eab75940dfd7cec259907006538`，减少以后上游变更引起的兼容性问题。

## Windows 本地启动（有权限使用目标数据时）

1. 安装 Git、Python 3.11+、[uv](https://docs.astral.sh/uv/getting-started/installation) 和 Node.js。准备可以访问小红书的 Chrome 浏览器。上游当前推荐 Chrome 144 或以上版本，并在 `chrome://inspect/#remote-debugging` 启用远程调试。
2. 在本仓库根目录新建 `.local` 文件夹，在 `.local/profile_url.txt` 中填写你在浏览器地址栏复制的**完整**目标主页链接。需要含 `xsec_token` 与 `xsec_source`，并保持用户 ID 为 `63572290000000001901d19a`。**不要提交 URL、Cookie、验证码或登录状态到 GitHub。**
3. 在 PowerShell 运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_local.ps1
```

首次运行可能要求在你自己的浏览器完成小红书登录或授权；脚本不绕过验证。

如果已经取得媒体素材的使用许可且确实需要图片、视频，可改为：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_local.ps1 -DownloadMedia
```

脚本最多尝试读取目标博主前 20 篇可获取的帖子，关闭评论采集，并使用单并发和间隔请求。**此限制只是首次验证，不是全部历史帖子。**

输出位于 `outputs/`：
- `all_posts.csv`：已采集帖子元数据（不是博主的全部历史帖子）。
- `agent_interview_candidates.csv`：标题、描述或标签包含面试相关关键词的候选帖。
- `image_review_queue.csv`：需要进一步识别图片或视频内容的候选资料。
- `analysis_input.jsonl`：后续 AI 结构化分析的输入。
- `summary.json`：数量统计、来源与过滤结果。

**注意**：小红书知识类笔记常把面试问题写在图片里。当前筛选只搜索标题、正文描述和标签，不会自动 OCR 图片和转写视频。即使输出为空，也不代表该博主没有 Agent 面试帖子。

## 仅运行离线数据分析

你也可以把通过授权导出的 `creator_contents_*.jsonl` 文件放在本地，直接运行：

```powershell
python scripts/filter_agent_posts.py --input-file "C:\path\to\creator_contents.jsonl" --output-dir outputs
```

不需要登录小红书。你也可以将生成的 Excel 或 JSONL 数据提供给 ChatGPT，进一步分析观点、论据和知识体系。

## GitHub Actions

本仓库的 Actions 在 push 时自动执行：
1. 单元测试（包含去重、关键词分类和 URL 校验）。
2. 托管运行器环境诊断并上传 `environment-report` Artifact。
3. 检出上游 MediaCrawler 固定版本，尝试 `uv sync` 和 `main.py --help`。

**不自动采集小红书用户数据**，因为 GitHub-hosted runners 没有本地授权会话，也不适合存放长期 Cookie 或无人值守绕过登录。

## 安全与合规

- 本仓库使用私有权限；`.gitignore` 排除 `.local/`、`vendor/`、`data/`、`outputs/` 和 `.env`。
- 不要上传 Cookies、登录二维码、手机号、一次性验证码等认证资料。
- MediaCrawler 的许可证为 `NON-COMMERCIAL LEARNING LICENSE 1.1`，并非通用自由软件许可证；必须遵守其非商业用途限制、平台规则与内容权利要求。
- 不使用代理池、自动通过验证码、绕过访问控制或高频抓取作为故障处理策略。


## GitHub Actions 手动二维码登录（可选）

当匿名浏览返回 `AUTH_REQUIRED` 时，**优先使用扫码**，无需输入手机号或 Cookie。

1. 在私有仓库的 **Actions** 页面，选中 **Manual QR login probe (single run only)**，点击 **Run workflow**。
2. 此工作流只在手动触发时启动。如果小红书返回安全限制，运行会直接停止；这不是登录弹窗，不能通过不断扫码解决。
3. 如果正常登录页面出现二维码，工作流会上传临时 `qr-login-challenge` Artifact，并在该次运行的 Summary 提供链接。下载解压后，用手机小红书 App 扫码确认。**二维码是短期身份验证挑战，只有有权限进入私有仓库的人员可以查看。**
4. 同一次任务等待扫码，成功后尝试打开指定博主主页并读取少量可见帖子卡片，结果保存在 `qr-login-result` Artifact。**不上传 Cookies、浏览器配置、长期凭证，也不保证能够访问帖子详情。**
5. 二维码可能先于等待时间过期；需要时只能由用户重新手动启动。扫码会话不会跨 GitHub Actions 任务持久化，每次新的运行都可能需要扫码。

推荐顺序：`Hosted browser research (no login)` → 若明确要求登录，手动启动 `Manual QR login probe (single run only)`。若是 `ACCESS_RESTRICTED`，直接停止；不尝试代理绕过或验证码自动化。

⚠️ **安全提示**：用于扫码的图片会暂存为 GitHub Artifact，设置保留 1 天。GitHub 仓库虽然是私有的，但能访问该运行记录的仓库协作者在有效期内也可能取得二维码。切勿将其分享到公共场所或外部聊天。授权过程中只运行已经审核的工作流代码。


## 登录管理模块（更新版）

手动运行 **Manual QR login probe (single run only)** 时，模块按以下顺序判断：

1. 先打开目标主页，判断平台安全限制、已有登录状态和匿名可访问的帖子卡片。
2. 如果只有普通登录弹窗，先尝试关闭一次；关闭后能看到帖子就继续匿名浏览。
3. 只有页面明确要求登录时，才打开官方登录界面，并优先寻找二维码入口；如果当前显示手机号登录，会尝试页面明确标注的二维码或其他登录方式入口。
4. 如果仍找不到二维码，保存脱敏的页面路径、标题、可见登录方式和候选元素信息，状态记为 `LOGIN_UI_NO_QR`，不再笼统写成 `QR_UNAVAILABLE`。
5. 如果发现安全限制，状态为 `ACCESS_RESTRICTED` 并停止；不会绕过验证码或访问控制。
6. 只有 `PUBLIC_ACCESS` 或 `AUTHENTICATED` 才会让工作流显示成功。二维码不可用、超时或安全限制会让工作流失败，并保留诊断 Artifact。

登录会话和 Cookie 不会写入 Artifact；二维码本身只在确认检测到后作为 1 天有效的临时 Artifact 上传。GitHub Runner 是临时环境，因此不会保存跨运行的登录状态。

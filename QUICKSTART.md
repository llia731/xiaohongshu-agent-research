# Windows 一键启动说明

这是一份独立的本地操作指南。目标：粘贴任意小红书博主完整主页链接，程序通过本地 Chrome 读取可访问的帖子，生成带原帖链接的资料索引；可选使用单独付费的大模型 API 进行知识分析。

## 首次使用

1. 安装 Python 3.11 或以上、Google Chrome。
2. 在 GitHub 仓库点击 Code → Download ZIP，解压到 Windows 文件夹。也可 git clone。
3. 在解压目录打开 PowerShell，执行：

    powershell -NoProfile -ExecutionPolicy Bypass -File .\start_windows.ps1

4. 等待依赖安装完成，访问 http://localhost:8501 。
5. 在页面粘贴完整主页链接，设置研究方向，点击“开始分析”。
6. 程序会打开一个专用 Chrome 窗口。能够匿名浏览时不登录；确实要求登录时，请在此窗口正常扫码授权。此浏览器登录状态仅保存在本地 .local/browser_profile 目录。
7. 页面将提供 report.md、analysis_input.json 和 manifest.json。请重点检查哪些帖子真正读到了正文。

不要把 Chrome 的登录目录、Cookie、验证码、二维码上传 GitHub。不要将普通 Chrome 现有用户配置目录传给 Playwright。

## 大模型报告

不配置 API Key 时会生成证据报告与主题索引，而不是自动推断作者的观点。你可以下载 analysis_input.json，上传 ChatGPT 继续深入分析。

如果你另外拥有 OpenAI API Key，可在当前 PowerShell 窗口设置：

    $env:OPENAI_API_KEY = "填入你的 API Key"
    $env:OPENAI_MODEL = "gpt-4.1-mini"
    powershell -NoProfile -ExecutionPolicy Bypass -File .\start_windows.ps1

然后勾选页面中的大模型报告选项。API 调用有独立费用，已读取的帖子文字会发送给 API 进行分析。

## 当前首版限制

- 只支持完整主页链接，不处理 xhslink 短链接。
- 初次建议最多 20 篇；页面滚动可能未覆盖全部历史笔记。
- 浏览器页面样式变化可能导致发现或正文提取失败。
- 图片 OCR、视频转写暂未实现，不得据此声称已读完全部内容。
- 只处理可以正常访问的内容，遇到平台安全限制时停止，不绕过身份验证。

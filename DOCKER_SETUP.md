# Docker 部署：Ubuntu 24.04 服务器

目标：在 10.150.150.152 上使用容器运行小红书博主研究工具，不在宿主机创建 Python 虚拟环境或安装浏览器。

## 1. 优先检查 Docker Engine 和 Compose

在服务器终端执行：

    docker --version
    docker compose version
    docker info --format 'Server: {{.ServerVersion}}'

若 docker 命令不存在，需管理员按 Docker 官方文档安装；若出现 permission denied，需管理员授权。Docker 组具有接近 root 的管理权限，不能随意添加用户。

此前 apt update 对 download.docker.com 出现 TLS 握手失败，只能说明该软件源本次更新失败，并不表示 Docker Engine 一定未安装。不要因此在共享服务器上升级全部系统软件。

## 2. 验证能否拉取镜像

    docker pull mcr.microsoft.com/playwright/python:v1.56.0-noble

这是 Microsoft 官方 Playwright 镜像，包含 Chromium 和 Linux 依赖。下载可能较大，请先确认服务器网络和磁盘空间。

## 3. 更新项目并启动

必须先下载 GitHub 仓库最新 ZIP 或 git pull。之前上传的旧 ZIP 未包含 Dockerfile 和 compose.yaml。

进入含有 Dockerfile、compose.yaml 的项目目录：

    docker compose -f compose.yaml config
    docker compose -f compose.yaml up -d --build
    docker compose -f compose.yaml ps
    docker compose -f compose.yaml logs --tail=80 researcher

Dockerfile 将 Python、Streamlit、Playwright Chromium、Xvfb、noVNC 安装在容器中，不要求宿主机安装 python3-venv、Playwright 或 Chromium。

Docker Compose 只把服务器 127.0.0.1 的端口发布出来：
- 8501：研究任务网页入口
- 6080：noVNC 浏览器画面，用于观察 Chrome 并在需要时扫码

## 4. 先检查容器是否能正常访问小红书

    docker compose -f compose.yaml exec -T researcher python -m scripts.test_server_access
    docker compose -f compose.yaml exec -T researcher cat .local/server_probe/report.json

这只测试公开主页，不登录，不获取帖子详情。容器通常仍使用与宿主机相同的公网出口，因此 Docker 不能保证避免小红书 IP 风险限制。若页面返回 ACCESS_RESTRICTED，应停止自动访问。

## 5. 从 Windows 访问容器里的网页和 Chrome

使用 MobaXterm Tunneling 新建两条 SSH Local 端口转发：
- 本地 8501 → 服务器 127.0.0.1:8501
- 本地 6080 → 服务器 127.0.0.1:6080

或者在 Windows PowerShell 新建 SSH 隧道：

    ssh -N -L 8501:127.0.0.1:8501 -L 6080:127.0.0.1:6080 liaoluoheng@10.150.150.152

随后从自己电脑打开：
- http://127.0.0.1:8501 （任务页面）
- http://127.0.0.1:6080/vnc.html （虚拟 Chrome 画面，点击 Connect）

先连接 noVNC，再在 Streamlit 页面点击开始分析。浏览器显示官方扫码入口时，可以从手机小红书 App 扫码。无需依赖 SSH X11 转发。

安全提醒：noVNC 默认未设置单独密码，只允许通过 SSH 隧道访问。不要将端口映射为 0.0.0.0，也不要在其他机器直接暴露 6080。共享服务器需要管理员确认本机其他用户对 localhost 服务的访问风险。

## 6. 数据与运行状态

浏览器登录资料和报告分别保存在 Docker 命名卷中；重启与重建容器通常不会清除。

    docker compose -f compose.yaml restart researcher
    docker compose -f compose.yaml down

不要使用 docker compose down -v，否则会删除登录资料及研究报告。

首版限制：仍未实现图片 OCR、视频转写和历史帖子的完整覆盖，未配置模型 API 时仅生成可追溯的主题与原帖索引。

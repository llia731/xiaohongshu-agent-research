# Ubuntu 24.04 服务器部署说明

本项目支持在有正常访问权限的 Ubuntu 服务器上进行公开内容研究。首次先验证服务器的网页访问能力；出现平台安全限制应停止，不要配置代理池或反复请求。

## 第一阶段：连通性验证

在服务器 SSH 终端执行：

    getent ahostsv4 www.xiaohongshu.com
    curl -L -sS -o /dev/null --connect-timeout 10 --max-time 20 -w 'HTTP: %{http_code}\nFinal URL: %{url_effective}\n' 'https://www.xiaohongshu.com/user/profile/63572290000000001901d19a'
    echo "$DISPLAY"
    python3 --version

HTTP 200 不代表帖子能被读取，必须检查浏览器渲染结果。

## 第二阶段：部署与 Playwright 渲染测试

    git clone https://github.com/llia731/xiaohongshu-agent-research.git
    cd xiaohongshu-agent-research
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements-local.txt
    .venv/bin/python -m playwright install chromium
    .venv/bin/python -m scripts.test_server_access
    cat .local/server_probe/report.json

测试不登录、不采集帖子详情。截图保存在服务器上的 .local/server_probe/browser_page.png。此目录被 Git 忽略，不会被自动提交。如果 Playwright 缺少系统依赖，请管理员根据启动错误安装，不要贸然升级整台生产服务器。

状态解读：
- ACCESS_RESTRICTED：IP 或访问安全限制，停止自动化请求。
- AUTH_REQUIRED：需要登录；之后才评估是否能扫码。
- LOGIN_PROMPT：登录弹窗，需在正常图形浏览器中判断关闭后可否继续。
- PUBLIC_ACCESS：能识别公开帖子链接，可以考虑少量试读。
- UNKNOWN：页面可能尚未加载或布局变化，应查看截图。
- BROWSER_TEST_ERROR：浏览器安装、系统依赖或沙箱运行问题。

## 第三阶段：启动交互式网页

在第二阶段确认正常访问后：

    bash start_linux.sh

为了保护端口，本服务只监听服务器本机 127.0.0.1:8501。请在 MobaXterm 的 Tunneling 中创建 SSH 本地端口转发：本地 8501 → 服务器 127.0.0.1:8501，再通过自己电脑浏览器访问 http://127.0.0.1:8501 。

扫码需要服务器有可用的图形显示环境。虽然 MobaXterm 可以启用 X11 forwarding，但仍要检查 DISPLAY 和 Chrome 是否能够弹出。推荐在专用服务器用户下运行，避免把会话资料目录交给其他账户。登录资料仅保存在服务器的 .local/browser_profile；不得提交 GitHub。

特别注意：SSH 端口转发仅传输网页界面，不会让服务器访问小红书时使用你自己电脑的出口 IP。即使服务器内网 IP 是 10.150.150.152，小红书看到的也可能是 NAT 网关的公网 IP。

本项目仍是首版：图片 OCR 和视频转写未完成，不能声称覆盖全部历史帖子。

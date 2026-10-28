$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "请先安装 Python 3.11 或更高版本，安装时勾选 Add Python to PATH。"
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw "创建虚拟环境失败" }
}
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $py -m pip install --disable-pip-version-check -r requirements-local.txt
if ($LASTEXITCODE -ne 0) { throw "安装依赖失败" }
Write-Host "运行地址：http://localhost:8501"
Write-Host "浏览器会话只保存在本机 .local/browser_profile"
& $py -m streamlit run app.py --server.address localhost --server.port 8501

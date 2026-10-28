param(
  [switch]$DownloadMedia
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# The profile link is read only from the current session or a local untracked file.
if (-not $env:XHS_PROFILE_URL) {
  $file = '.local/profile_url.txt'
  if (Test-Path $file) {
    $env:XHS_PROFILE_URL = (Get-Content $file -Raw).Trim()
  }
}
if (-not $env:XHS_PROFILE_URL) {
  throw "请将完整博主主页 URL（含 xsec_token 和 xsec_source）写入 .local/profile_url.txt，或设置 XHS_PROFILE_URL 环境变量。"
}

$upstream = 'vendor/MediaCrawler'
$sha = '68d9ef1c1da22eab75940dfd7cec259907006538'
if (-not (Test-Path "$upstream/.git")) {
  New-Item -ItemType Directory -Path 'vendor' -Force | Out-Null
  git clone https://github.com/NanmiCoder/MediaCrawler.git $upstream
  if ($LASTEXITCODE -ne 0) { throw 'MediaCrawler 仓库下载失败' }
}
# Restore the files so generated overrides are not appended more than once.
git -C $upstream fetch origin $sha
if ($LASTEXITCODE -ne 0) { throw '上游版本获取失败' }
git -C $upstream checkout --force $sha
if ($LASTEXITCODE -ne 0) { throw '上游版本检出失败' }

$flags = @()
if ($DownloadMedia) { $flags += '--download-media' }
python scripts/configure_mediacrawler.py --upstream-dir $upstream @flags
if ($LASTEXITCODE -ne 0) { throw '本地配置失败' }

Push-Location $upstream
try {
  uv sync
  if ($LASTEXITCODE -ne 0) { throw '依赖安装失败' }
  uv run main.py --platform xhs --lt qrcode --type creator --save_data_option jsonl
  if ($LASTEXITCODE -ne 0) { throw '采集命令未正常结束' }
}
finally {
  Pop-Location
}
python scripts/filter_agent_posts.py --input-dir vendor/MediaCrawler/data/xhs/jsonl --output-dir outputs
if ($LASTEXITCODE -ne 0) { throw '结果整理失败' }
Write-Host '完成。查看 outputs/ 下的 CSV、JSONL 与 summary.json。'

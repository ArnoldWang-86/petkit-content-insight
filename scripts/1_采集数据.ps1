. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "步骤 1 / 采集数据"

$node = Require-Node

$statePath = "data\raw\_collect_state.json"
$doneCount = 0
if (Test-Path $statePath) {
    try { $doneCount = (Get-Content $statePath -Encoding utf8 | ConvertFrom-Json).done.Count } catch { $doneCount = 0 }
}
$remain = 35 - $doneCount

Write-Host "  数据源   B站公开搜索接口（未登录即可访问的公开信息）" -ForegroundColor Gray
Write-Host "  关键词   35 个（品类词 / 品牌词 / 痛点场景词）" -ForegroundColor Gray
Write-Host "  已完成   $doneCount 个，待采集 $remain 个" -ForegroundColor White
Write-Host ""
Write-Host "  提示：本文件会一直采到全部完成（约 $([math]::Round($remain * 4)) 分钟）。" -ForegroundColor Yellow
Write-Host "        想中途停下就按 Ctrl+C，已采数据不会丢，下次接着采。" -ForegroundColor Gray
Write-Host ""
$go = Read-Host "  开始采集？(y/n)"
if ($go -ne 'y' -and $go -ne 'Y') { Write-Host "  已取消"; Start-Sleep -Seconds 1; exit 0 }
Write-Host ""

$env:PAGES = "10"
& $node "src\collect.js"
$env:PAGES = ""

Write-Host ""
Write-Host "  ---------- 当前总进度 ----------" -ForegroundColor White
& $node "src\progress.js"
Show-NextStep "3_清洗数据.bat"
Stop-Pause

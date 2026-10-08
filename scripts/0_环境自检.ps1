. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "步骤 0 / 环境自检"

$node = Find-Node
if (-not $node) {
    Show-Err "没有找到 Node.js"
    Write-Host ""
    Show-Hint "本项目用 Node 做采集与分析（它自带网络请求能力，不需要另装第三方库）。"
    Show-Hint "安装：打开 https://nodejs.org 下载 LTS 版，一路下一步。"
    Show-Hint "装完关掉本窗口，重新双击本文件。"
    Stop-Pause
    exit 1
}
Show-OK "Node.js 就绪"
Show-Hint "$node"
& $node --version | ForEach-Object { Show-Hint "版本 $_" }
Write-Host ""

Show-Step "检查网络与 B站公开接口 ..."
& $node "src\probe.js" | ForEach-Object { Show-Hint $_ }
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Show-Err "连不上 B站公开接口"
    Show-Hint "先确认浏览器能正常打开 bilibili.com，然后重新运行本文件。"
    Stop-Pause
    exit 1
}

Write-Host ""
Show-OK "环境检查通过，可以开始采集"
Show-NextStep "1_采集数据.bat"
Stop-Pause

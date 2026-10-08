. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "步骤 2 / 采集进度"
$node = Require-Node
& $node "src\progress.js"
Stop-Pause

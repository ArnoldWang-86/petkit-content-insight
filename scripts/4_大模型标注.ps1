. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "步骤 4 / 大模型标注"

$py = Require-Python
Show-Hint "解释器: $py"
Write-Host ""
Show-Step "调用 DeepSeek 对全部记录做三维标注（每批落盘，可断点续跑）"
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
& $py "src\py\step1_label.py"
$code = $LASTEXITCODE
$env:PYTHONIOENCODING = ""

if ($code -ne 0) {
    Show-Err "本步骤失败，请查看上方错误信息"
    Stop-Pause
    exit $code
}
Show-NextStep "5_大模型投票.bat"
Stop-Pause

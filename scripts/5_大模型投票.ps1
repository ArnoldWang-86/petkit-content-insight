. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "步骤 5 / 大模型投票"

$py = Require-Python
Show-Hint "解释器: $py"
Write-Host ""
Show-Step "对低置信度样本做自一致性投票（问 3 次取多数）"
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
& $py "src\py\step2_vote.py"
$code = $LASTEXITCODE
$env:PYTHONIOENCODING = ""

if ($code -ne 0) {
    Show-Err "本步骤失败，请查看上方错误信息"
    Stop-Pause
    exit $code
}
Show-NextStep "6_聚合标注.bat"
Stop-Pause

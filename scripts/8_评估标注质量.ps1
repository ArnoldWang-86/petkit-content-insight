. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "步骤 8 / 评估标注质量"

$py = Require-Python
Show-Hint "解释器: $py"
Write-Host ""
Show-Step "算准确率 + Wilson 置信区间 + 实测各规则精度"
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
& $py "src\py\step5_eval.py"
$code = $LASTEXITCODE
$env:PYTHONIOENCODING = ""

if ($code -ne 0) {
    Show-Err "本步骤失败，请查看上方错误信息"
    Stop-Pause
    exit $code
}
Show-NextStep "9_跑分析.bat"
Stop-Pause

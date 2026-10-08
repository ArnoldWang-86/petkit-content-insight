. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "步骤 7 / 生成抽检表"

$py = Require-Python
Show-Hint "解释器: $py"
Write-Host ""
Show-Step "抽取 200 条分层随机（度量）+ 100 条主动学习（改进）"
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
& $py "src\py\step4_sample.py"
$code = $LASTEXITCODE
$env:PYTHONIOENCODING = ""

if ($code -ne 0) {
    Show-Err "本步骤失败，请查看上方错误信息"
    Stop-Pause
    exit $code
}
Show-NextStep "打开CSV人工核对，然后跑 8_评估标注质量.bat"
Stop-Pause

. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "步骤 6 / 聚合标注"

$py = Require-Python
Show-Hint "解释器: $py"
Write-Host ""
Show-Step "把规则投票与大模型投票按权重合并，产出最终标签"
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
& $py "src\py\step3_aggregate.py"
$code = $LASTEXITCODE
$env:PYTHONIOENCODING = ""

if ($code -ne 0) {
    Show-Err "本步骤失败，请查看上方错误信息"
    Stop-Pause
    exit $code
}
Show-NextStep "7_生成抽检表.bat"
Stop-Pause

. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "步骤 9 / 五路分析"

$py = Require-Python
Show-Hint "解释器: $py"
Write-Host ""
Show-Step "执行 src/py/analyze.py（产品线 / 品牌声量 / 用户痛点 / 内容策略 / 场景）"
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
& $py "src\py\analyze.py"
$code = $LASTEXITCODE
$env:PYTHONIOENCODING = ""

if ($code -ne 0) {
    Show-Err "分析失败"
    Stop-Pause
    exit $code
}
Write-Host ""
Show-OK "分析完成，结果在 results/ 目录"
Show-Hint "只有 final_label 为 A 的记录才用于产品线结论；B/C 用于需求与语境分析"
Stop-Pause

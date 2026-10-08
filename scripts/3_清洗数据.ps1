. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "步骤 3 / 数据清洗与规则标注"

$py = Require-Python
Show-Hint "解释器: $py"
Write-Host ""
Show-Step "执行 src/py/clean.py ..."
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
& $py "src\py\clean.py"
$code = $LASTEXITCODE
$env:PYTHONIOENCODING = ""

if ($code -ne 0) {
    Show-Err "清洗失败"
    Stop-Pause
    exit $code
}
Write-Host ""
Show-OK "清洗完成"
Show-NextStep "4_大模型标注.bat"
Stop-Pause

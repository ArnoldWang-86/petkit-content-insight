. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "评估标注质量"

$py = Require-Python
$env:PYTHONIOENCODING = "utf-8"
& $py "src\py\step5_eval.py"
$code = $LASTEXITCODE
$env:PYTHONIOENCODING = ""
if ($code -ne 0) { Show-Err "评估失败"; Stop-Pause; exit $code }
Stop-Pause

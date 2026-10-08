. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "标注流程（一键跑完 4-7 步）"

$py = Require-Python
Show-Hint "解释器: $py"
Write-Host ""
Show-Hint "本文件依次执行：大模型标注 -> 自一致性投票 -> 聚合 -> 生成抽检表"
Show-Hint "其中标注步骤支持断点续跑，已跑过的部分不会重复调用 API。"
Write-Host ""
$go = Read-Host "  开始？(y/n)"
if ($go -ne 'y' -and $go -ne 'Y') { Write-Host "  已取消"; Start-Sleep -Seconds 1; exit 0 }

$env:PYTHONIOENCODING = "utf-8"
$steps = @(
    @("步骤4 大模型标注", "src\py\step1_label.py"),
    @("步骤5 自一致性投票", "src\py\step2_vote.py"),
    @("步骤6 加权投票聚合", "src\py\step3_aggregate.py"),
    @("步骤7 生成抽检表", "src\py\step4_sample.py")
)
foreach ($s in $steps) {
    Write-Host ""
    Write-Host ("================================================================") -ForegroundColor Cyan
    Write-Host ("   " + $s[0]) -ForegroundColor Cyan
    Write-Host ("================================================================") -ForegroundColor Cyan
    & $py $s[1]
    if ($LASTEXITCODE -ne 0) {
        Show-Err ($s[0] + " 失败，已中断")
        $env:PYTHONIOENCODING = ""
        Stop-Pause
        exit $LASTEXITCODE
    }
}
$env:PYTHONIOENCODING = ""

Write-Host ""
Show-OK "标注流程全部完成"
Write-Host ""
Show-Hint "请打开 results/人工抽检_300条_方案B.csv"
Show-Hint "在「人工核对(填A/B/C/N)」列填入 A / B / C / N"
Show-Hint "然后运行 run_eval.bat 评估标注质量"
Stop-Pause

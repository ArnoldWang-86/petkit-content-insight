. "$PSScriptRoot\_common.ps1"
Set-Location (Join-Path $PSScriptRoot "..")
Show-Title "一键跑完：清洗 → 标注 → 投票 → 聚合 → 抽检"

$py = Require-Python
Show-Hint "解释器: $py"
Write-Host ""
Show-Hint "本文件依次执行 5 步，全程自动，中途可 Ctrl+C 中断。"
Show-Hint "标注步骤支持断点续跑：已完成的批次不会重复调用 API。"
Write-Host ""
Show-Hint "预计耗时：首次约 40 分钟；若已有检查点则快很多。"
Write-Host ""
$go = Read-Host "  开始？(y/n)"
if ($go -ne 'y' -and $go -ne 'Y') { Write-Host "  已取消"; Start-Sleep -Seconds 1; exit 0 }

$env:PYTHONIOENCODING = "utf-8"
$steps = @(
    @("步骤1 清洗数据（应用新词典）", "src\py\clean.py"),
    @("步骤2 大模型标注", "src\py\step1_label.py"),
    @("步骤3 自一致性投票", "src\py\step2_vote.py"),
    @("步骤4 加权投票聚合", "src\py\step3_aggregate.py"),
    @("步骤5 生成抽检表", "src\py\step4_sample.py")
)
$n = 0
foreach ($s in $steps) {
    $n++
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ("   [" + $n + "/" + $steps.Count + "] " + $s[0]) -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    & $py $s[1]
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Show-Err ($s[0] + " 失败，流程中断")
        Show-Hint "修复后可重新运行本文件，已完成的批次会从断点继续"
        $env:PYTHONIOENCODING = ""
        Stop-Pause
        exit $LASTEXITCODE
    }
}
$env:PYTHONIOENCODING = ""

Write-Host ""
Show-OK "全流程完成"
Write-Host ""
Show-Hint "下一步：打开 results/人工抽检_300条_方案B.csv"
Show-Hint "在「人工核对(填A/B/C/N)」列填入 A / B / C / N（对照 docs/人工核对速查卡）"
Show-Hint "填完后双击 run_eval.bat 评估标注质量"
Stop-Pause

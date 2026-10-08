# _common.ps1 —— 各步骤共用的小工具
$ErrorActionPreference = 'Continue'
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Show-Title($t) {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "   $t" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
}
function Show-Step($t) { Write-Host "  $t" -ForegroundColor White }
function Show-OK($t)   { Write-Host "  [完成] $t" -ForegroundColor Green }
function Show-Warn($t) { Write-Host "  [注意] $t" -ForegroundColor Yellow }
function Show-Err($t)  { Write-Host "  [错误] $t" -ForegroundColor Red }
function Show-Hint($t) { Write-Host "        $t" -ForegroundColor Gray }

function Find-Node {
    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($d in @("D:\nodejs", "$env:ProgramFiles\nodejs", "$env:LOCALAPPDATA\Programs\nodejs")) {
        if ($d -and (Test-Path (Join-Path $d "node.exe"))) { return (Join-Path $d "node.exe") }
    }
    return $null
}
function Require-Node {
    $n = Find-Node
    if (-not $n) {
        Show-Err "没有找到 Node.js"
        Write-Host ""
        Show-Hint "安装：打开 https://nodejs.org 下载 LTS 版，一路下一步。"
        Show-Hint "装完关掉本窗口，重新双击本文件。"
        Write-Host ""
        Read-Host "  按回车关闭"
        exit 1
    }
    return $n
}
# 找一个装了必需库的 Python
# 注意：Windows 自带一个「微软商店占位程序」python.exe（路径含 WindowsApps），
#       它被执行时什么都不做，却会让 Test-Path 以为找到了 Python —— 必须排除。
function Find-Python {
    $cands = @()
    # 1) 显式候选优先（python.org 官方安装包的默认位置）
    $cands += "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
    $cands += "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    $cands += "D:\Python313\python.exe"
    # 2) PATH 里的 python，但排除微软商店占位程序
    foreach ($c in @(Get-Command python -All -ErrorAction SilentlyContinue)) {
        if ($c.Source -and $c.Source -notmatch 'WindowsApps') { $cands += $c.Source }
    }
    # 3) 逐个实跑验证：必须真能启动并报出主版本号 3（占位程序过不了这一关）
    foreach ($p in $cands) {
        if (-not ($p -and (Test-Path $p))) { continue }
        try {
            $ver = & $p -c "import sys;print(sys.version_info[0])" 2>$null
            if ("$ver" -eq "3") { return $p }
        } catch { }
    }
    return $null
}
function Require-Python {
    $p = Find-Python
    if (-not $p) {
        Show-Err "没有找到 Python"
        Show-Hint "安装：https://www.python.org 下载 3.10+ 版本"
        Read-Host "  按回车关闭"
        exit 1
    }
    return $p
}

function Stop-Pause { Write-Host ""; Read-Host "  按回车关闭" }
function Show-NextStep($t) {
    Write-Host ""
    Write-Host "  ------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "  下一步：双击「$t」" -ForegroundColor Yellow
    Write-Host "  ------------------------------------------------------------" -ForegroundColor DarkGray
}

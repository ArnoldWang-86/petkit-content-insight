@echo off
chcp 65001 >nul
title 步骤7 生成抽检表
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\7_生成抽检表.ps1"
if errorlevel 1 pause

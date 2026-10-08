@echo off
chcp 65001 >nul
title 步骤9 五路分析
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\9_跑分析.ps1"
if errorlevel 1 pause

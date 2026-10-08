@echo off
chcp 65001 >nul
title 步骤4 大模型标注
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\4_大模型标注.ps1"
if errorlevel 1 pause

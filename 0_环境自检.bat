@echo off
chcp 65001 >nul
title 步骤0 环境自检
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\0_环境自检.ps1"
if errorlevel 1 pause

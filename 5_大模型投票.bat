@echo off
chcp 65001 >nul
title 步骤5 大模型投票
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\5_大模型投票.ps1"
if errorlevel 1 pause

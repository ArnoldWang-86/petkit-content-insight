@echo off
chcp 65001 >nul
title 步骤3 数据清洗
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\3_清洗数据.ps1"
if errorlevel 1 pause

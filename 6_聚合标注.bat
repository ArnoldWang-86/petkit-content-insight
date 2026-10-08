@echo off
chcp 65001 >nul
title 步骤6 聚合标注
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\6_聚合标注.ps1"
if errorlevel 1 pause

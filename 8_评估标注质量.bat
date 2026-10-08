@echo off
chcp 65001 >nul
title 步骤8 评估标注质量
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\8_评估标注质量.ps1"
if errorlevel 1 pause

@echo off
chcp 65001 >nul
title 步骤2 查看采集进度
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\2_查看进度.ps1"
if errorlevel 1 pause

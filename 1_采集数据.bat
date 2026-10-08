@echo off
chcp 65001 >nul
title 步骤1 采集数据
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\1_采集数据.ps1"
if errorlevel 1 pause

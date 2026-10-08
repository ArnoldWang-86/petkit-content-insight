@echo off
chcp 65001 >nul
title 一键跑完标注全流程
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_all.ps1"
if errorlevel 1 pause

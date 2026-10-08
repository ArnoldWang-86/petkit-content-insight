@echo off
chcp 65001 >nul
title Evaluate Labels
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_eval.ps1"
if errorlevel 1 pause

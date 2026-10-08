@echo off
chcp 65001 >nul
title Labeling Pipeline
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_labeling.ps1"
if errorlevel 1 pause

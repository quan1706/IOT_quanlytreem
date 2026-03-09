@echo off
chcp 65001 >nul
color 0b
title SMART BABY CARE SERVER
set PYTHONIOENCODING=utf-8

echo ==============================================
echo       KHOI DONG SMART BABY CARE SERVER
echo ==============================================

REM Them ffmpeg vao PATH
set PATH=%PATH%;C:\Users\Admin\miniconda3\Scripts

cd "%~dp0\server_python\main\xiaozhi-server"
echo Dang khoi dong Server tai thu muc: %CD%
echo Bam Ctrl+C de dung lai bat cu luc nao...
echo.

python app.py

echo.
pause

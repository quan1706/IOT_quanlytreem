@echo off
chcp 65001 >nul
title Smart Baby Care - Server

echo ============================================================
echo   Smart Baby Care Server - Python 3.11
echo ============================================================
echo.

:: Giải phóng port 8003 nếu đang bị chiếm
echo [1/3] Kiem tra port 8003...
powershell -NoProfile -Command "$p = Get-NetTCPConnection -LocalPort 8003 -ErrorAction SilentlyContinue | Select-Object -First 1; if ($p) { Stop-Process -Id $p.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host 'Da giai phong port 8003.' } else { Write-Host 'Port 8003 san sang.' }"

:: Di chuyển vào thư mục server
echo [2/3] Chuyen thu muc...
cd /d E:\IOT_BANMOI\IOT_quanlytreem\server_python\main\xiaozhi-server

:: Chạy server với encoding UTF-8
echo [3/3] Khoi dong server...
echo.
echo  Dashboard : http://localhost:8003
echo  WebSocket : ws://localhost:8000/xiaozhi/v1/
echo.
echo  Nhan Ctrl+C de dung server.
echo ============================================================

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
venv\Scripts\python.exe app.py

pause

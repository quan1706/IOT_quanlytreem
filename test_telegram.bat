@echo off
chcp 65001 >nul
title Smart Baby Care - Full Simulation Tool
color 0b

echo ==================================================
echo      GIẢ LẬP CẢNH BÁO SMART BABY CARE (V4)
echo     (Phát hiện khóc qua Mic + Camera + AI)
echo ==================================================
echo.
echo [1] Script sẽ giả lập ESP32 Mic gửi tín hiệu qua WebSocket.
echo [2] Script sẽ giả lập ESP32-CAM gửi ảnh qua HTTP.
echo.
echo 💡 Bạn có thể kéo thả 1 file ảnh vào đây để test Camera,
echo    hoặc nhấn Enter luôn để dùng ảnh mặc định.
echo.

set /p IMG_PATH="Nhập đường dẫn ảnh (hoặc Enter): "

:: Sử dụng python -X utf8 để hiển thị đúng ký tự Unicode trên Windows
python -X utf8 simulation_test\full_simulator.py %IMG_PATH%

echo.
echo ==================================================
echo Nhấn phím bất kỳ để kết thúc...
pause >nul

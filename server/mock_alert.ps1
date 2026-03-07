# 2. Cấu hình URL (Dùng cổng 9999 theo NetBeans)
$url = "http://localhost:9999/server/cry"

if (-not (Test-Path "baby.jpg")) {
    Write-Host "ERR: Khong tim thay file baby.jpg! Hay copy mot anh vao day." -ForegroundColor Red
    return
}

# 2. Gửi request POST Multipart đến Server

Write-Host "Dang gui canh bao gia lap..." -ForegroundColor Cyan
# Dung --form va quotes de tranh loi PowerShell voi ky tu @
& curl.exe -X POST $url `
    --form "image=@baby.jpg" `
    --form "label=baby_cry"

Write-Host "`nHoan thanh! Hay kiem tra Telegram cua ban." -ForegroundColor Green

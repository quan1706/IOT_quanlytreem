# Script giả lập Telegram Webhook gửi callback về Server

# Gia lap nguoi dung bam nut "Phat nhac"
$url = "http://localhost:9999/server/telegram/callback"

$json = @{
    callback_query = @{
        data = "phat_nhac"
    }
} | ConvertTo-Json

Write-Host "Dang gia lap bam nut 'Phat nhac'..." -ForegroundColor Cyan
Invoke-RestMethod -Uri $url -Method Post -Body $json -ContentType "application/json"

Write-Host "Hoan thanh! Kiem tra log Server de xem lenh da gui den ESP32 chua." -ForegroundColor Green

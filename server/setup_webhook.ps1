# Script setup Webhook cho Telegram Bot
# Sử dụng: powershell -File .\setup_webhook.ps1 -NgrokUrl "https://xxxx.ngrok-free.app"

param (
    [Parameter(Mandatory=$true)]
    [string]$NgrokUrl
)

# Đọc cấu hình từ file properties (hoặc fix cứng nếu cần)
$token = "8765806795:AAEB83HSeGkpYYv0JsnnPz6IaiSCvlDOn_w"
$webhookPart = "/server/telegram/callback"
$fullUrl = $NgrokUrl + $webhookPart

Write-Host "--- THIẾT LẬP TELEGRAM WEBHOOK ---" -ForegroundColor Cyan
Write-Host "URL đích: $fullUrl" -ForegroundColor Yellow

$apiUri = "https://api.telegram.org/bot$token/setWebhook?url=$fullUrl"

Write-Host "Đang gọi Telegram API..."
$response = Invoke-RestMethod -Uri $apiUri -Method Get

if ($response.ok) {
    Write-Host "THANH CONG: $fullUrl đã được đăng ký với Telegram." -ForegroundColor Green
    Write-Host "Mô tả: $($response.description)"
} else {
    Write-Host "THAT BAI: $($response.description)" -ForegroundColor Red
}

Write-Host "`nLưu ý: Bạn phải đang chạy ngrok expose 9999 trên máy của mình." -ForegroundColor Gray

# Script giả lập người dùng bấm nút trên Telegram
$url = "http://localhost:9999/server/telegram/callback"

$jsonPayload = @{
    callback_query = @{
        id = "123456789"
        from = @{
            id = 987654321
            first_name = "Blue"
            last_name = "Hoang"
        }
        message = @{
            chat = @{
                id = "-5283283687"
            }
        }
        data = "phat_nhac"
    }
} | ConvertTo-Json -Depth 5

Write-Host "Dang gui gia lap nut bam Telegram (Phat nhac)..." -ForegroundColor Cyan

$bytes = [System.Text.Encoding]::UTF8.GetBytes($jsonPayload)
& curl.exe -X POST $url `
    -H "Content-Type: application/json" `
    -d $jsonPayload

Write-Host "`nHoan thanh! Hay kiem tra Dashboard va Telegram của bạn." -ForegroundColor Green

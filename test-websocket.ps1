# 🧪 WebSocket Connection Test Script
# Tests the WebSocket endpoint after fixing the Redis subscription blocking issue

Write-Host "🔌 WebSocket Connection Test" -ForegroundColor Cyan
Write-Host "============================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Test API Gateway Health
Write-Host "Step 1: Check API Gateway Health" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
    Write-Host "✅ API Gateway: HTTP $($response.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "❌ API Gateway: Not accessible" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 2: Test Authentication
Write-Host "Step 2: Test Authentication" -ForegroundColor Yellow
try {
    $loginResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" -Method Post -ContentType "application/json" -Body '{"email":"admin@example.com","password":"admin123"}'

    if ($loginResponse.access_token) {
        Write-Host "✅ Authentication: Successful" -ForegroundColor Green
        $token = $loginResponse.access_token
        Write-Host "   Token: $($token.Substring(0, 20))..." -ForegroundColor Gray
    } else {
        Write-Host "❌ Authentication: Failed (no token)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Authentication: Failed" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 3: Test WebSocket Connection
Write-Host "Step 3: Test WebSocket Connection" -ForegroundColor Yellow

# Use .NET WebSocket for testing
try {
    $wsUrl = "ws://localhost:8000/ws?token=$token"
    Write-Host "   Connecting to: $wsUrl" -ForegroundColor Gray

    # Create WebSocket connection
    $ws = New-Object System.Net.WebSockets.ClientWebSocket
    $cts = New-Object System.Threading.CancellationTokenSource

    # Connect with timeout
    $connectTask = $ws.ConnectAsync($wsUrl, $cts.Token)
    $timeoutTask = (Start-Sleep -Seconds 5).GetAwaiter().GetResult()

    # Wait for connection or timeout
    $completedTask = (Wait-Task -Task $connectTask -Timeout 5)

    if ($ws.State -eq "Open") {
        Write-Host "✅ WebSocket: Connected successfully" -ForegroundColor Green
        Write-Host "   State: $($ws.State)" -ForegroundColor Gray

        # Send a ping message
        $buffer = [System.Text.Encoding]::UTF8.GetBytes("ping")
        $sendTask = $ws.SendAsync($buffer, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts.Token)

        # Receive response
        $receiveBuffer = [Array]::CreateInstance([byte], 1024)
        $receiveTask = $ws.ReceiveAsync($receiveBuffer, $cts.Token)

        Write-Host "   Ping sent, waiting for pong..." -ForegroundColor Gray

        # Close connection
        $ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "Test complete", $cts.Token).Wait()
        Write-Host "   Connection closed cleanly" -ForegroundColor Gray
    } else {
        Write-Host "❌ WebSocket: Connection failed" -ForegroundColor Red
        Write-Host "   State: $($ws.State)" -ForegroundColor Red
    }

    $cts.Dispose()
    $ws.Dispose()

} catch {
    Write-Host "❌ WebSocket: Exception occurred" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# Step 4: Test Job Submission API
Write-Host "Step 4: Test Job Submission API" -ForegroundColor Yellow
try {
    $jobResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/jobs" -Method Post -ContentType "application/json" -Headers @{"Authorization"="Bearer $token"} -Body '{"prompt":"Test WebSocket connection"}'

    if ($jobResponse.job_id) {
        Write-Host "✅ Job Submission: Successful" -ForegroundColor Green
        Write-Host "   Job ID: $($jobResponse.job_id)" -ForegroundColor Gray
        Write-Host "   Status: $($jobResponse.status)" -ForegroundColor Gray
        Write-Host "   Message: $($jobResponse.message)" -ForegroundColor Gray
    } else {
        Write-Host "❌ Job Submission: Failed (no job_id)" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Job Submission: Failed" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "🎉 WebSocket Test Complete" -ForegroundColor Green
Write-Host "============================" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. Check frontend: http://localhost:3000" -ForegroundColor Gray
Write-Host "   2. Try submitting a job through the UI" -ForegroundColor Gray
Write-Host "   3. Monitor WebSocket connection in browser DevTools" -ForegroundColor Gray
Write-Host "   4. Check API Gateway logs: docker compose logs api-gateway" -ForegroundColor Gray
Write-Host ""
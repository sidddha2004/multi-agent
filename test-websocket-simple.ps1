# 🔌 WebSocket Connection Test (Simple Version)
# Tests the key components for WebSocket connectivity

Write-Host "🔌 WebSocket Connectivity Test" -ForegroundColor Cyan
Write-Host "===============================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Test API Gateway Health
Write-Host "Step 1: Check API Gateway Health" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
    Write-Host "✅ API Gateway: HTTP $($response.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "❌ API Gateway: Not accessible" -ForegroundColor Red
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
    } else {
        Write-Host "❌ Authentication: Failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Authentication: Failed" -ForegroundColor Red
    Write-Host "   Note: Create admin user first if it doesn't exist" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Step 3: Test WebSocket Endpoint Accessibility
Write-Host "Step 3: Test WebSocket Endpoint Accessibility" -ForegroundColor Yellow
try {
    # Try to upgrade connection to WebSocket (this will fail but endpoint should be reachable)
    $wsUrl = "ws://localhost:8000/ws?token=$token"
    Write-Host "   WebSocket URL: $wsUrl" -ForegroundColor Gray

    # Test if the host is reachable
    $uri = [System.Uri]$wsUrl
    $tcpConnection = New-Object System.Net.Sockets.TcpClient
    try {
        $tcpConnection.Connect($uri.Host, $uri.Port)
        Write-Host "✅ WebSocket Endpoint: Port is accessible" -ForegroundColor Green
        $tcpConnection.Close()
    } catch {
        Write-Host "❌ WebSocket Endpoint: Port not accessible" -ForegroundColor Red
    }

} catch {
    Write-Host "❌ WebSocket Endpoint: Error" -ForegroundColor Red
}

Write-Host ""

# Step 4: Test Job Submission API
Write-Host "Step 4: Test Job Submission API" -ForegroundColor Yellow
try {
    $jobResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/jobs" -Method Post -ContentType "application/json" -Headers @{"Authorization"="Bearer $token"} -Body '{"prompt":"Test WebSocket fix"}'

    if ($jobResponse.job_id) {
        Write-Host "✅ Job Submission: Successful" -ForegroundColor Green
        Write-Host "   Job ID: $($jobResponse.job_id)" -ForegroundColor Gray
        Write-Host "   Status: $($jobResponse.status)" -ForegroundColor Gray

        # Test job status endpoint
        $statusResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/jobs/$($jobResponse.job_id)" -Method Get -Headers @{"Authorization"="Bearer $token"}
        Write-Host "✅ Job Status Query: Successful" -ForegroundColor Green
        Write-Host "   Tasks: $($statusResponse.tasks.Count)" -ForegroundColor Gray
    } else {
        Write-Host "❌ Job Submission: Failed" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Job Submission: Failed" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# Step 5: Check Docker Container Status
Write-Host "Step 5: Check Docker Container Status" -ForegroundColor Yellow
$containers = @("api-gateway", "frontend")
foreach ($container in $containers) {
    $status = docker ps --filter "name=$container" --format "{{.Status}}"
    if ($status) {
        Write-Host "✅ $container : $status" -ForegroundColor Green
    } else {
        Write-Host "❌ $container : Not running" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "🎉 Backend Test Complete" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Manual Frontend WebSocket Test:" -ForegroundColor Cyan
Write-Host "   1. Open browser: http://localhost:3000" -ForegroundColor Gray
Write-Host "   2. Open Developer Tools (F12)" -ForegroundColor Gray
Write-Host "   3. Go to Console tab" -ForegroundColor Gray
Write-Host "   4. Login with credentials" -ForegroundColor Gray
Write-Host "   5. Look for WebSocket connection messages" -ForegroundColor Gray
Write-Host "   6. Submit a test job" -ForegroundColor Gray
Write-Host "   7. Check if WebSocket stays connected" -ForegroundColor Gray
Write-Host ""
Write-Host "🔧 If WebSocket Still Fails:" -ForegroundColor Yellow
Write-Host "   1. Rebuild API Gateway: docker compose build api-gateway" -ForegroundColor Gray
Write-Host "   2. Restart service: docker compose restart api-gateway" -ForegroundColor Gray
Write-Host "   3. Check logs: docker compose logs api-gateway" -ForegroundColor Gray
Write-Host "   4. Clear browser cache and reload" -ForegroundColor Gray
Write-Host ""
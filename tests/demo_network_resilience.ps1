# Live Demo: Network Resilience
# This script demonstrates the network resilience feature in action

$RALPH_DIR = ".ralph-mode"
$MOCK_FILE = "$RALPH_DIR/mock_network_down"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "🎬 LIVE DEMO: NETWORK RESILIENCE" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Ensure ralph mode is enabled
if (-not (Test-Path "$RALPH_DIR/state.json")) {
    Write-Host "❌ Ralph Mode not enabled. Run this first:" -ForegroundColor Red
    Write-Host '   python ralph_mode.py enable "Test task" --max-iterations 5' -ForegroundColor Yellow
    exit 1
}

# Load network check function
$NETWORK_CHECK_HOSTS = @("api.github.com", "github.com", "1.1.1.1")

function Test-InternetConnection {
    if (Test-Path "$RALPH_DIR/mock_network_down") {
        return $false
    }
    foreach ($h in $NETWORK_CHECK_HOSTS) {
        try {
            if (Test-Connection -ComputerName $h -Count 1 -Quiet -ErrorAction SilentlyContinue) { 
                return $true 
            }
        } catch { }
    }
    return $false
}

function Wait-ForInternet {
    $waitTime = 2  # Fast for demo
    $maxWait = 10
    $totalWaited = 0
    $attempt = 1
    
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host "🔌 Network connection lost - waiting for reconnection..." -ForegroundColor Yellow
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host ""
    
    while (-not (Test-InternetConnection)) {
        $timestamp = Get-Date -Format "HH:mm:ss"
        Write-Host "[$timestamp] Attempt ${attempt}: Waiting ${waitTime}s for network... (total: ${totalWaited}s)" -ForegroundColor Magenta
        
        Start-Sleep -Seconds $waitTime
        $totalWaited += $waitTime
        $attempt++
        
        # Exponential backoff (capped for demo)
        $waitTime = [Math]::Min($waitTime * 2, $maxWait)
    }
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host ""
    Write-Host "[$timestamp] ✅ Network connection restored after ${totalWaited}s!" -ForegroundColor Green
    Write-Host ""
}

Write-Host "📋 Demo Scenario:" -ForegroundColor Green
Write-Host "─────────────────────────────────────────────────────────────────"
Write-Host "  1. Start simulated iteration"
Write-Host "  2. Network goes DOWN (simulated)"
Write-Host "  3. Ralph waits with exponential backoff"
Write-Host "  4. Network comes back UP"
Write-Host "  5. Ralph continues!"
Write-Host ""
Write-Host "Press any key to start..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Write-Host ""

# Simulate iterations
for ($iter = 1; $iter -le 3; $iter++) {
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "🔄 ITERATION $iter" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    
    # Check network before iteration
    Write-Host "🌐 Checking network before iteration..." -ForegroundColor Blue
    
    if (-not (Test-InternetConnection)) {
        Wait-ForInternet
    } else {
        Write-Host "✅ Network is available" -ForegroundColor Green
    }
    Write-Host ""
    
    # Simulate work
    Write-Host "⚙️ Working on task..." -ForegroundColor White
    Start-Sleep -Seconds 1
    
    # On iteration 2, simulate network outage
    if ($iter -eq 2) {
        Write-Host ""
        Write-Host "💥 [DEMO] Simulating network outage NOW!" -ForegroundColor Red
        "Network down for demo at $(Get-Date)" | Set-Content $MOCK_FILE
        
        Start-Sleep -Seconds 1
        
        # Try to continue, will detect network is down
        Write-Host ""
        Write-Host "🌐 Checking network..." -ForegroundColor Blue
        
        if (-not (Test-InternetConnection)) {
            # Start a background job to restore network after 8 seconds
            $job = Start-Job -ScriptBlock {
                param($mockFile)
                Start-Sleep -Seconds 8
                Remove-Item $mockFile -Force -ErrorAction SilentlyContinue
            } -ArgumentList $MOCK_FILE
            
            Wait-ForInternet
            
            # Cleanup job
            Stop-Job $job -ErrorAction SilentlyContinue
            Remove-Job $job -ErrorAction SilentlyContinue
        }
    }
    
    Write-Host "✅ Iteration $iter complete!" -ForegroundColor Green
    Write-Host ""
    
    if ($iter -lt 3) {
        Write-Host "💤 Sleeping 1 second before next iteration..." -ForegroundColor Gray
        Start-Sleep -Seconds 1
    }
}

# Cleanup
Remove-Item $MOCK_FILE -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "🎉 DEMO COMPLETE!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "The network resilience feature successfully:" -ForegroundColor White
Write-Host "  ✅ Detected network outage" -ForegroundColor Green
Write-Host "  ✅ Waited with exponential backoff" -ForegroundColor Green
Write-Host "  ✅ Auto-detected network restoration" -ForegroundColor Green
Write-Host "  ✅ Resumed iteration automatically" -ForegroundColor Green
Write-Host ""

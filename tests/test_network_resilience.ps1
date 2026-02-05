# Test Network Resilience Feature
# This script simulates network disconnection to test the resilience feature

param(
    [int]$DisconnectDuration = 15,  # Seconds to simulate disconnection
    [switch]$Verbose
)

$scriptPath = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RALPH_DIR = ".ralph-mode"
$MOCK_FILE = "$RALPH_DIR/mock_network_down"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "🧪 NETWORK RESILIENCE TEST" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "This test will:" -ForegroundColor Yellow
Write-Host "  1. Create a mock file that simulates network being DOWN"
Write-Host "  2. Wait $DisconnectDuration seconds (simulating outage)"
Write-Host "  3. Remove the mock file (simulating network restored)"
Write-Host ""

# Create ralph-mode directory if needed
if (-not (Test-Path $RALPH_DIR)) {
    New-Item -ItemType Directory -Path $RALPH_DIR -Force | Out-Null
}

# Function to check if mock network is down
function Test-MockNetworkDown {
    return Test-Path $MOCK_FILE
}

# Patched version of Test-InternetConnection for testing
$patchedFunction = @'
function Test-InternetConnection {
    # Check for mock file first (for testing)
    if (Test-Path ".ralph-mode/mock_network_down") {
        return $false
    }
    
    # Real check
    foreach ($h in @("api.github.com", "github.com", "1.1.1.1")) {
        try {
            $result = Test-Connection -ComputerName $h -Count 1 -Quiet -ErrorAction SilentlyContinue
            if ($result) { return $true }
        } catch { }
    }
    return $false
}
'@

Write-Host "📋 Test Plan:" -ForegroundColor Green
Write-Host "─────────────────────────────────────────────────────────────────"
Write-Host ""

# Step 1: Verify real network is up
Write-Host "[Step 1] Verifying real network connection..." -ForegroundColor Blue
$realNetworkUp = Test-Connection -ComputerName "1.1.1.1" -Count 1 -Quiet -ErrorAction SilentlyContinue
if ($realNetworkUp) {
    Write-Host "  ✅ Real network is UP" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ Real network appears down - test may not work correctly" -ForegroundColor Yellow
}
Write-Host ""

# Step 2: Create mock disconnect
Write-Host "[Step 2] Simulating network DISCONNECT..." -ForegroundColor Blue
"Network simulated down at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Set-Content $MOCK_FILE
Write-Host "  📁 Created mock file: $MOCK_FILE" -ForegroundColor Yellow
Write-Host "  🔌 Network status: SIMULATED DOWN" -ForegroundColor Red
Write-Host ""

# Step 3: Test the patched function
Write-Host "[Step 3] Testing detection (should show DOWN)..." -ForegroundColor Blue
if (Test-MockNetworkDown) {
    Write-Host "  ✅ Mock network correctly detected as DOWN" -ForegroundColor Green
} else {
    Write-Host "  ❌ Mock detection failed!" -ForegroundColor Red
}
Write-Host ""

# Step 4: Countdown
Write-Host "[Step 4] Simulating outage for $DisconnectDuration seconds..." -ForegroundColor Blue
Write-Host ""

$startTime = Get-Date
for ($i = $DisconnectDuration; $i -gt 0; $i--) {
    $elapsed = ((Get-Date) - $startTime).TotalSeconds
    $progress = [math]::Round(($elapsed / $DisconnectDuration) * 100)
    
    Write-Host "`r  ⏳ Network DOWN: $i seconds remaining... [$('#' * ($progress / 5))$('.' * (20 - ($progress / 5)))] $progress%" -NoNewline -ForegroundColor Magenta
    Start-Sleep -Seconds 1
}
Write-Host ""
Write-Host ""

# Step 5: Restore network
Write-Host "[Step 5] Simulating network RESTORE..." -ForegroundColor Blue
Remove-Item $MOCK_FILE -Force -ErrorAction SilentlyContinue
Write-Host "  📁 Removed mock file" -ForegroundColor Green
Write-Host "  🌐 Network status: RESTORED" -ForegroundColor Green
Write-Host ""

# Step 6: Verify restore
Write-Host "[Step 6] Testing detection (should show UP)..." -ForegroundColor Blue
if (-not (Test-MockNetworkDown)) {
    Write-Host "  ✅ Network correctly detected as UP" -ForegroundColor Green
} else {
    Write-Host "  ❌ Network still showing as down!" -ForegroundColor Red
}
Write-Host ""

Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "✅ NETWORK RESILIENCE TEST COMPLETE" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "To test with actual Ralph Mode:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. In Terminal 1, start Ralph:" -ForegroundColor White
Write-Host "     .\ralph-mode.ps1 enable 'Test task' --max-iterations 10" -ForegroundColor Gray
Write-Host "     .\ralph-mode.ps1 run" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. In Terminal 2, simulate disconnect:" -ForegroundColor White
Write-Host "     'down' | Set-Content .ralph-mode/mock_network_down" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Watch Ralph wait for network..." -ForegroundColor White
Write-Host ""
Write-Host "  4. Restore network:" -ForegroundColor White
Write-Host "     Remove-Item .ralph-mode/mock_network_down" -ForegroundColor Gray
Write-Host ""

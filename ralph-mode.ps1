# Copilot Ralph Mode - PowerShell Wrapper
# Full support for GitHub Copilot CLI features
# Network resilience with automatic retry
# Usage: .\ralph-mode.ps1 <command> [options]

param(
    [Parameter(Position=0)]
    [string]$Command,
    
    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

# Configuration
$RALPH_DIR = ".ralph-mode"
$STATE_FILE = "$RALPH_DIR/state.json"
$CHECKPOINT_FILE = "$RALPH_DIR/checkpoint.json"
$COPILOT_CMD = "copilot"

# Network resilience settings
$NETWORK_CHECK_HOSTS = @("api.github.com", "github.com", "1.1.1.1")
$NETWORK_RETRY_INITIAL = 5
$NETWORK_RETRY_MAX = 300
$NETWORK_RETRY_MULTIPLIER = 2
$MAX_CONSECUTIVE_FAILURES = 3

# Colors
function Write-Color {
    param([string]$Text, [string]$Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

# ═══════════════════════════════════════════════════════════════
# Network Resilience Functions
# ═══════════════════════════════════════════════════════════════

function Test-InternetConnection {
    # Check for mock file first (for testing)
    if (Test-Path "$RALPH_DIR/mock_network_down") {
        return $false
    }
    
    foreach ($h in $NETWORK_CHECK_HOSTS) {
        try {
            $result = Test-Connection -ComputerName $h -Count 1 -Quiet -ErrorAction SilentlyContinue
            if ($result) { return $true }
        } catch { }
        
        try {
            $response = Invoke-WebRequest -Uri "https://$h" -Method Head -TimeoutSec 5 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) { return $true }
        } catch { }
    }
    return $false
}

function Wait-ForInternet {
    $waitTime = $NETWORK_RETRY_INITIAL
    $totalWaited = 0
    $attempt = 1
    
    Write-Host ""
    Write-Color "═══════════════════════════════════════════════════════════════" -Color Yellow
    Write-Color "🔌 Network connection lost - waiting for reconnection..." -Color Yellow
    Write-Color "═══════════════════════════════════════════════════════════════" -Color Yellow
    Write-Host ""
    
    # Save checkpoint
    Save-Checkpoint "network_disconnected"
    
    while (-not (Test-InternetConnection)) {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Write-Host "[$timestamp] Attempt $attempt`: Waiting ${waitTime}s for network... (total: ${totalWaited}s)" -ForegroundColor Magenta
        
        Start-Sleep -Seconds $waitTime
        $totalWaited += $waitTime
        $attempt++
        
        # Exponential backoff
        $waitTime = [Math]::Min($waitTime * $NETWORK_RETRY_MULTIPLIER, $NETWORK_RETRY_MAX)
    }
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host ""
    Write-Color "[$timestamp] ✅ Network connection restored after ${totalWaited}s!" -Color Green
    Write-Host ""
    
    # Small delay to ensure stable connection
    Start-Sleep -Seconds 2
    
    Save-Checkpoint "network_restored"
}

function Save-Checkpoint {
    param([string]$Status)
    
    $state = Get-RalphState
    $iteration = if ($state) { $state.iteration } else { 0 }
    
    $checkpoint = @{
        status = $Status
        iteration = $iteration
        timestamp = (Get-Date -Format "o")
        pid = $PID
    }
    
    New-Item -ItemType Directory -Force -Path $RALPH_DIR | Out-Null
    $checkpoint | ConvertTo-Json | Set-Content $CHECKPOINT_FILE -Encoding UTF8
}

function Clear-Checkpoint {
    if (Test-Path $CHECKPOINT_FILE) {
        Remove-Item $CHECKPOINT_FILE -Force -ErrorAction SilentlyContinue
    }
}

function Test-Checkpoint {
    if (Test-Path $CHECKPOINT_FILE) {
        $checkpoint = Get-Content $CHECKPOINT_FILE | ConvertFrom-Json
        if ($checkpoint.status -eq "network_disconnected" -or $checkpoint.status -eq "iteration_failed") {
            Write-Color "📌 Found checkpoint at iteration $($checkpoint.iteration) (status: $($checkpoint.status))" -Color Yellow
            return $true
        }
    }
    return $false
}

# ═══════════════════════════════════════════════════════════════
# End Network Resilience Functions
# ═══════════════════════════════════════════════════════════════

function Show-Help {
    Write-Color "🔄 Copilot Ralph Mode - PowerShell" -Color Green
    Write-Host ""
    Write-Host "Commands for state management:"
    Write-Host "  .\ralph-mode.ps1 enable `"prompt`" --max-iterations 20"
    Write-Host "  .\ralph-mode.ps1 enable `"prompt`" --max-iterations 20 --auto-agents"
    Write-Host "  .\ralph-mode.ps1 disable"
    Write-Host "  .\ralph-mode.ps1 status"
    Write-Host "  .\ralph-mode.ps1 iterate"
    Write-Host ""
    Write-Host "Commands for running loops:"
    Write-Host "  .\ralph-mode.ps1 run [--agent <name>]"
    Write-Host "  .\ralph-mode.ps1 single"
    Write-Host "  .\ralph-mode.ps1 resume"
    Write-Host "  .\ralph-mode.ps1 check-network"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  --auto-agents             Enable dynamic sub-agent creation"
    Write-Host "  --completion-promise      Phrase that signals completion"
    Write-Host "  --no-network-check        Disable network resilience"
    Write-Host ""
    Write-Host "Network Resilience:"
    Write-Host "  - Auto-detects connection loss"
    Write-Host "  - Waits with exponential backoff"
    Write-Host "  - Resumes from checkpoint"
    Write-Host ""
    Write-Host "See README.md for full documentation."
}

function Test-RalphActive {
    return Test-Path $STATE_FILE
}

function Get-RalphState {
    if (Test-RalphActive) {
        return Get-Content $STATE_FILE | ConvertFrom-Json
    }
    return $null
}

function Invoke-RalphLoop {
    param(
        [string]$Agent = "",
        [int]$Sleep = 2,
        [bool]$NetworkCheck = $true
    )
    
    if (-not (Test-RalphActive)) {
        Write-Color "❌ Ralph mode is not active. Enable it first." -Color Red
        return
    }
    
    Write-Color "🔄 RALPH LOOP STARTING" -Color Green
    Write-Host "Press Ctrl+C to stop"
    if ($NetworkCheck) {
        Write-Host "Network resilience: ENABLED" -ForegroundColor Cyan
    }
    Write-Host ""
    
    # Check for checkpoint
    if (Test-Checkpoint) {
        Write-Color "📌 Resuming from checkpoint..." -Color Yellow
    }
    
    # Initial network check
    if ($NetworkCheck) {
        Write-Host "🌐 Checking network connectivity..." -ForegroundColor Blue
        if (Test-InternetConnection) {
            Write-Color "✅ Network connection verified" -Color Green
        } else {
            Write-Color "⚠️ No network connection" -Color Yellow
            Wait-ForInternet
        }
        Write-Host ""
    }
    
    $consecutiveFailures = 0
    
    while (Test-RalphActive) {
        $state = Get-RalphState
        $iteration = $state.iteration
        $maxIter = $state.max_iterations
        
        if ($maxIter -gt 0 -and $iteration -gt $maxIter) {
            Write-Color "⚠️ Max iterations reached" -Color Yellow
            Clear-Checkpoint
            break
        }
        
        # Network check before iteration
        if ($NetworkCheck -and -not (Test-InternetConnection)) {
            Wait-ForInternet
        }
        
        Write-Color "🔄 Ralph Iteration $iteration" -Color Cyan
        
        # Save checkpoint
        Save-Checkpoint "iteration_started"
        
        # Build copilot command
        $context = Get-Content "$RALPH_DIR/prompt.md" -Raw
        $copilotArgs = @("-p", $context, "--allow-all-tools", "--allow-all-paths")
        
        if ($Agent) {
            $copilotArgs += @("--agent=$Agent")
        }
        
        # Run copilot with error handling
        $success = $true
        try {
            & $COPILOT_CMD @copilotArgs 2>&1 | Tee-Object -FilePath "$RALPH_DIR/output.txt"
            $exitCode = $LASTEXITCODE
            
            if ($exitCode -ne 0) {
                $output = Get-Content "$RALPH_DIR/output.txt" -Raw -ErrorAction SilentlyContinue
                
                # Check for network-related errors
                if ($output -match "network|connection|timeout|unreachable|resolve" -or $exitCode -in @(6, 7, 28, 56)) {
                    Write-Color "⚠️ Network error detected" -Color Yellow
                    if ($NetworkCheck) {
                        Save-Checkpoint "network_error"
                        Wait-ForInternet
                        $consecutiveFailures++
                        continue
                    }
                }
                $success = $false
            }
        } catch {
            Write-Color "⚠️ Error running Copilot: $_" -Color Yellow
            $success = $false
        }
        
        if ($success) {
            $consecutiveFailures = 0
            Clear-Checkpoint
            
            # Check for completion
            $output = Get-Content "$RALPH_DIR/output.txt" -Raw -ErrorAction SilentlyContinue
            $promise = $state.completion_promise
            
            if ($promise -and $output -match "<promise>$promise</promise>") {
                Write-Color "✅ COMPLETION PROMISE DETECTED!" -Color Green
                python "$scriptPath\ralph_mode.py" complete $output
                Clear-Checkpoint
                break
            }
            
            # Increment iteration
            python "$scriptPath\ralph_mode.py" iterate
        } else {
            $consecutiveFailures++
            Write-Color "⚠️ Iteration failed (consecutive: $consecutiveFailures/$MAX_CONSECUTIVE_FAILURES)" -Color Yellow
            
            if ($consecutiveFailures -ge $MAX_CONSECUTIVE_FAILURES) {
                Write-Color "❌ Too many consecutive failures. Stopping." -Color Red
                Write-Color "💡 Resume with: .\ralph-mode.ps1 resume" -Color Cyan
                Save-Checkpoint "max_failures_reached"
                break
            }
            
            if ($NetworkCheck -and -not (Test-InternetConnection)) {
                Wait-ForInternet
            }
        }
        
        if (Test-RalphActive) {
            Write-Host "💤 Sleeping $Sleep seconds..."
            Start-Sleep -Seconds $Sleep
        }
    }
    
    Write-Color "🏁 Ralph loop finished" -Color Green
}

function Test-NetworkCmd {
    Write-Host "🌐 Checking network connectivity..." -ForegroundColor Blue
    Write-Host ""
    
    foreach ($netHost in $NETWORK_CHECK_HOSTS) {
        Write-Host "  Testing $netHost... " -NoNewline
        $pingOk = Test-Connection -ComputerName $netHost -Count 1 -Quiet -ErrorAction SilentlyContinue
        if ($pingOk) {
            Write-Color "✅ OK (ping)" -Color Green
        } else {
            try {
                $response = Invoke-WebRequest -Uri "https://$netHost" -Method Head -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
                Write-Color "✅ OK (https)" -Color Green
            } catch {
                Write-Color "❌ FAILED" -Color Red
            }
        }
    }
    
    Write-Host ""
    if (Test-InternetConnection) {
        Write-Color "✅ Network is available" -Color Green
    } else {
        Write-Color "❌ Network is NOT available" -Color Red
    }
}

# Main
switch ($Command) {
    "run" {
        Invoke-RalphLoop
    }
    "single" {
        if (Test-RalphActive) {
            $state = Get-RalphState
            Write-Color "🔄 Running single iteration..." -Color Cyan
            
            # Network check
            if (-not (Test-InternetConnection)) {
                Wait-ForInternet
            }
            
            $context = Get-Content "$RALPH_DIR/prompt.md" -Raw
            & $COPILOT_CMD -p $context --allow-all-tools --allow-all-paths | Tee-Object -FilePath "$RALPH_DIR/output.txt"
            python "$scriptPath\ralph_mode.py" iterate
        } else {
            Write-Color "❌ Ralph mode not active" -Color Red
        }
    }
    "resume" {
        if (Test-Checkpoint) {
            Write-Color "📌 Resuming from checkpoint..." -Color Yellow
            if (-not (Test-InternetConnection)) {
                Wait-ForInternet
            }
        }
        Invoke-RalphLoop
    }
    "check-network" {
        Test-NetworkCmd
    }
    "help" {
        Show-Help
    }
    default {
        # Pass through to Python script
        python "$scriptPath\ralph_mode.py" $Command @Arguments
    }
}
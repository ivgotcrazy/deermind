[CmdletBinding()]
param(
    [Parameter(Position=0)][ValidateSet('start','stop','status','setup','restart')][string]$Action = 'start',
    [ValidateSet('student','parent','admin')][string]$Role = 'student',
    [ValidateRange(1024,65535)][int]$Port = 5181,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $projectRoot)
$serverPath = Join-Path $PSScriptRoot 'serve.mjs'
$stateDir = Join-Path $repoRoot '.tmp\mvp-prototype-next'
$statePath = Join-Path $stateDir "$Port.json"
$logPath = Join-Path $stateDir "$Port.log"
$errorPath = Join-Path $stateDir "$Port-error.log"
$url = "http://127.0.0.1:$Port/$Role/"
$started = $null

function Get-OwnedServer {
    if (-not (Test-Path -LiteralPath $statePath)) { return $null }
    try {
        $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $proc = Get-Process -Id ([int]$saved.processId) -ErrorAction Stop
        $details = Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)"
        if ($proc.StartTime.ToUniversalTime().Ticks.ToString() -ne [string]$saved.startedTicks) { return $null }
        if (-not $details.CommandLine.Contains($serverPath)) { return $null }
        return $proc
    } catch { return $null }
}

function Test-Ready($Process) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/__prototype_health" -TimeoutSec 2
        return ($health.name -eq 'deermind-mvp-prototype-next' -and $health.pid -eq $Process.Id -and $health.root.TrimEnd('\','/') -eq $projectRoot.TrimEnd('\','/'))
    } catch { return $false }
}

function Stop-Owned($Process) {
    if ($Process) {
        Stop-Process -Id $Process.Id -ErrorAction Stop
        $Process.WaitForExit()
        Write-Host "Stopped new preview (PID $($Process.Id))."
    }
    if (Test-Path -LiteralPath $statePath) { Remove-Item -LiteralPath $statePath }
}

function Build-Apps {
    if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw 'Install Node.js 22.12+ (or 20.19+) and npm first.'
    }
    foreach ($app in @('student','parent','admin')) {
        $appRoot = Join-Path $projectRoot $app
        $stamp = Join-Path $appRoot 'node_modules\.deermind-lock-hash'
        $algorithm = [Security.Cryptography.SHA256]::Create()
        try { $hash = [BitConverter]::ToString($algorithm.ComputeHash([IO.File]::ReadAllBytes((Join-Path $appRoot 'package-lock.json')))).Replace('-', '') }
        finally { $algorithm.Dispose() }
        $installed = if (Test-Path -LiteralPath $stamp) { (Get-Content -LiteralPath $stamp -Raw).Trim() } else { '' }
        Push-Location $appRoot
        try {
            if ($installed -ne $hash -or -not (Test-Path -LiteralPath 'node_modules\vite\bin\vite.js')) {
                Write-Host "Installing pinned $app dependencies..."
                $installArgs = @('ci', '--no-audit', '--no-fund', '--prefer-offline')
                # The original admin lock pins plugin-vue 5 with Vite 7. Preserve that
                # baseline for M01; validate its build instead of silently upgrading it.
                if ($app -eq 'admin') { $installArgs += '--legacy-peer-deps' }
                & npm.cmd @installArgs
                if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed for $app." }
                Set-Content -LiteralPath $stamp -Value $hash -Encoding ASCII
            }
            Write-Host "Checking and building $app..."
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw "Build failed for $app; no new server was started." }
        } finally { Pop-Location }
    }
}

try {
    if ($Port -eq 5178) { throw 'Port 5178 is reserved for the existing preview. Use 5181 for the new baseline.' }
    $running = Get-OwnedServer
    if ($Action -eq 'stop') { Stop-Owned $running; exit 0 }
    if ($Action -eq 'status') {
        if ($running -and (Test-Ready $running)) {
            Write-Host "Running new V2 preview (PID $($running.Id))."
            Write-Host "Student: http://127.0.0.1:$Port/student/"
            Write-Host "Parent: http://127.0.0.1:$Port/parent/"
            Write-Host "Admin: http://127.0.0.1:$Port/admin/"
        } elseif ($running) { throw 'The owned process is running but health verification failed.' }
        else { Write-Host 'New V2 preview is not running.' }
        exit 0
    }
    if ($running -and $Action -eq 'start') {
        if (-not (Test-Ready $running)) { throw 'Owned process is not ready. Use restart.' }
        Write-Host "Already running: $url"
        if (-not $NoBrowser) { Start-Process $url }
        exit 0
    }
    if ($running -and $Action -eq 'setup') { throw 'Stop the preview before rebuilding, or use restart.' }
    if ($Action -eq 'restart') { Stop-Owned $running }
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
    Build-Apps
    if ($Action -eq 'setup') { Write-Host 'All three apps are ready. Run prototype.cmd start.'; exit 0 }
    $started = Start-Process -FilePath (Get-Command node).Source -ArgumentList @('"' + $serverPath + '"', '--port', [string]$Port) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $logPath -RedirectStandardError $errorPath
    $ticks = $started.StartTime.ToUniversalTime().Ticks.ToString()
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $started.Refresh()
        if ($started.HasExited) { throw "Preview exited. See $errorPath (check port and configuration)." }
        if (Test-Ready $started) { $ready = $true; break }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) { throw "Preview did not become ready. See $errorPath." }
    @{processId=$started.Id; startedTicks=$ticks; port=$Port; project=$projectRoot} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding ASCII
    Write-Host "Student: http://127.0.0.1:$Port/student/"
    Write-Host "Parent: http://127.0.0.1:$Port/parent/"
    Write-Host "Admin: http://127.0.0.1:$Port/admin/"
    Write-Host 'Math-6b live chat is connected. Page statistics remain V2 demonstration data.'
    if (-not $NoBrowser) { Start-Process $url }
} catch {
    if ($started) {
        $started.Refresh()
        if (-not $started.HasExited) { Stop-Process -Id $started.Id }
    }
    Write-Error $_.Exception.Message
    exit 1
}

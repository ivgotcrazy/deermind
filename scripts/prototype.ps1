[CmdletBinding()]
param(
    [Parameter(Position=0)][ValidateSet('start','stop','status','setup')][string]$Action = 'start',
    [ValidateSet('student','parent','admin')][string]$Role = 'student',
    [ValidateRange(1024,65535)][int]$Port = 5178,
    [switch]$Lan,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Join-Path $repoRoot 'src\mvp_prototype'
$serverPath = Join-Path $projectRoot 'scripts\serve.mjs'
$stateDir = Join-Path $repoRoot '.tmp'
$statePath = Join-Path $stateDir "mvp-prototype-$Port.json"
$logPath = Join-Path $stateDir "mvp-prototype-$Port.log"
$errorPath = Join-Path $stateDir "mvp-prototype-$Port-error.log"
$homePage = @{ student = 'home'; parent = 'overview'; admin = 'dashboard' }[$Role]
$url = "http://127.0.0.1:$Port/#/$Role/$homePage"

function Get-OwnedServer {
    if (-not (Test-Path -LiteralPath $statePath)) { return $null }
    try {
        $record = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $serverProcess = Get-Process -Id ([int]$record.processId) -ErrorAction Stop
        $details = Get-CimInstance Win32_Process -Filter "ProcessId = $($serverProcess.Id)"
        if ($serverProcess.StartTime.ToUniversalTime().Ticks.ToString() -ne [string]$record.startedTicks) { return $null }
        if (-not $details.CommandLine.Contains($serverPath)) { return $null }
        return $serverProcess
    } catch { return $null }
}

try {
    $running = Get-OwnedServer
    if ($Action -eq 'stop') {
        if ($running) { Stop-Process -Id $running.Id -ErrorAction Stop; Write-Host "Prototype stopped (PID $($running.Id))." }
        else { Write-Host 'No owned prototype process is running.' }
        if (Test-Path -LiteralPath $statePath) { Remove-Item -LiteralPath $statePath }
        exit 0
    }
    if ($Action -eq 'status') {
        if ($running) { Write-Host "Prototype running (PID $($running.Id)): $url" }
        else { Write-Host 'Prototype is not running.' }
        exit 0
    }
    if ($running -and $Action -eq 'start') {
        $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        if ($Lan -and -not $saved.lan) { throw 'Already running on localhost. Run prototype.cmd stop, then start -Lan.' }
        Write-Host "Prototype already running: $url"
        if (-not $NoBrowser) { Start-Process $url }
        exit 0
    }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22.12+ (or 20.19+) first.' }
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'npm.cmd was not found. Check the Node.js installation.' }
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
    $lockPath = Join-Path $projectRoot 'package-lock.json'
    $stampPath = Join-Path $projectRoot 'node_modules\.deermind-lock-hash'
    $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try { $hash = [BitConverter]::ToString($hashAlgorithm.ComputeHash([IO.File]::ReadAllBytes($lockPath))).Replace('-', '') }
    finally { $hashAlgorithm.Dispose() }
    $stamp = if (Test-Path -LiteralPath $stampPath) { (Get-Content -LiteralPath $stampPath -Raw).Trim() } else { '' }
    Push-Location $projectRoot
    try {
        if ($stamp -ne $hash -or -not (Test-Path -LiteralPath 'node_modules\vite\bin\vite.js')) {
            Write-Host 'Installing pinned prototype dependencies (first launch or lockfile change)...'
            & npm.cmd ci --no-fund --no-audit
            if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network and retry.' }
            Set-Content -LiteralPath $stampPath -Value $hash -Encoding ASCII
        }
        Write-Host 'Checking types and building the prototype...'
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Prototype build failed; no server was started.' }
    } finally { Pop-Location }
    if ($Action -eq 'setup') { Write-Host 'Prototype is ready. Run prototype.cmd start.'; exit 0 }
    $bindAddress = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }
    $nodePath = (Get-Command node).Source
    $arguments = @('"' + $serverPath + '"', '--port', [string]$Port, '--host', $bindAddress)
    $started = Start-Process -FilePath $nodePath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $logPath -RedirectStandardError $errorPath
    $ticks = $started.StartTime.ToUniversalTime().Ticks.ToString()
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $started.Refresh()
        if ($started.HasExited) { throw "Prototype server exited. See $errorPath (the port may be occupied)." }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/__prototype_health" -TimeoutSec 1
            if ($health.name -eq 'deermind-mvp-prototype' -and $health.pid -eq $started.Id) { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) {
        $started.Refresh()
        if (-not $started.HasExited) { Stop-Process -Id $started.Id }
        throw "Prototype did not become ready. See $errorPath."
    }
    @{ processId = $started.Id; startedTicks = $ticks; port = $Port; lan = [bool]$Lan } | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding ASCII
    Write-Host "Prototype ready: $url"
    Write-Host "Stop with: prototype.cmd stop -Port $Port"
    if ($Lan) {
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } | ForEach-Object { Write-Host "LAN preview: http://$($_.IPAddress):$Port/#/$Role/$homePage" }
        Write-Host 'LAN mode exposes only synthetic prototype data. Use your trusted local network.'
    }
    if (-not $NoBrowser) { Start-Process $url }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}

[CmdletBinding()]
param(
    [Parameter(Position=0)][ValidateSet('start','stop','status','restart','setup')][string]$Action = 'start',
    [ValidateRange(1024,65535)][int]$Port = 5182,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$serverPath = Join-Path $PSScriptRoot 'serve.mjs'
$stateDir = Join-Path $projectRoot '.tmp'
$stateFile = Join-Path $stateDir "$Port.json"
$url = "http://127.0.0.1:$Port/admin/#/textbooks"
$started = $null

function Get-OwnedServer {
    if (-not (Test-Path -LiteralPath $stateFile)) { return $null }
    try {
        $saved = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        $process = Get-Process -Id ([int]$saved.processId) -ErrorAction Stop
        $details = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)"
        if ($process.StartTime.ToUniversalTime().Ticks.ToString() -ne [string]$saved.startedTicks -or -not $details.CommandLine.Contains($serverPath)) { return $null }
        return $process
    } catch { return $null }
}
function Test-Ready($Process) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/__m1_health" -TimeoutSec 2
        return ($health.name -eq 'deermind-m1-prototype' -and $health.pid -eq $Process.Id -and $health.root.TrimEnd('\','/') -eq $projectRoot.TrimEnd('\','/'))
    } catch { return $false }
}
function Stop-Owned($Process) {
    if ($Process) { Stop-Process -Id $Process.Id; $Process.WaitForExit() }
    if (Test-Path -LiteralPath $stateFile) { Remove-Item -LiteralPath $stateFile }
}
try {
    $running = Get-OwnedServer
    if ($Action -eq 'stop') { Stop-Owned $running; Write-Host 'M1 preview stopped.'; exit 0 }
    if ($Action -eq 'status') {
        if ($running -and (Test-Ready $running)) { Write-Host "Running M1 preview: $url" }
        else { Write-Host 'M1 preview is not running.' }
        exit 0
    }
    if ($running -and $Action -eq 'start') {
        if (-not (Test-Ready $running)) { throw 'M1 process is not ready. Use restart.' }
        Write-Host "Already running: $url"
        if (-not $NoBrowser) { Start-Process $url }
        exit 0
    }
    if ($running -and $Action -eq 'setup') { throw 'Stop M1 preview before setup, or use restart.' }
    if ($Action -eq 'restart') { Stop-Owned $running }
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
    Push-Location $projectRoot
    try {
        $algorithm = [Security.Cryptography.SHA256]::Create()
        try { $lockHash = [BitConverter]::ToString($algorithm.ComputeHash([IO.File]::ReadAllBytes((Join-Path $projectRoot 'package-lock.json')))).Replace('-', '') }
        finally { $algorithm.Dispose() }
        $stamp = Join-Path $stateDir 'installed-lock.txt'
        $previousHash = if (Test-Path -LiteralPath $stamp) { (Get-Content -LiteralPath $stamp -Raw).Trim() } else { '' }
        if ($lockHash -ne $previousHash -or -not (Test-Path -LiteralPath 'node_modules/vite/bin/vite.js')) {
            & npm.cmd ci --no-audit --no-fund --prefer-offline
            if ($LASTEXITCODE -ne 0) { throw 'M1 dependency installation failed.' }
            Set-Content -LiteralPath $stamp -Value $lockHash -Encoding ASCII
        }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'M1 build failed; preview was not started.' }
    } finally { Pop-Location }
    if ($Action -eq 'setup') { Write-Host 'M1 build ready.'; exit 0 }
    $started = Start-Process -FilePath (Get-Command node).Source -ArgumentList @('"' + $serverPath + '"', '--port', [string]$Port) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $stateDir "$Port.log") -RedirectStandardError (Join-Path $stateDir "$Port-error.log")
    $ticks = $started.StartTime.ToUniversalTime().Ticks.ToString()
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $started.Refresh()
        if ($started.HasExited) { throw 'M1 preview exited. Check the port and .tmp error log.' }
        if (Test-Ready $started) { $ready = $true; break }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) { throw 'M1 preview did not become ready.' }
    @{processId=$started.Id;startedTicks=$ticks;port=$Port} | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding ASCII
    Write-Host "M1 preview: $url"
    if (-not $NoBrowser) { Start-Process $url }
} catch {
    if ($started) { $started.Refresh(); if (-not $started.HasExited) { Stop-Process -Id $started.Id } }
    Write-Error $_.Exception.Message
    exit 1
}

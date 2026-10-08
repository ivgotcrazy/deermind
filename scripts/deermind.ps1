[CmdletBinding()]
param(
    [Parameter(Position=0)][ValidateSet('start','stop','status','setup')][string]$Action = 'start',
    [ValidateSet('real','scripted')][string]$Mode,
    [ValidateRange(1024,65535)][int]$Port = 8765,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$')][string]$Name = 'default',
    [switch]$NewSession,
    [switch]$NoBrowser,
    [ValidateRange(1,1000000)][int]$Quantity = 6,
    [ValidateRange(1,100000000)][int]$Total = 42,
    [ValidateRange(1,1000000)][int]$Target = 15,
    [string]$Noun,
    [ValidateRange(0,100000)][int]$MaxCalls = 0,
    [ValidateRange(0,10000)][double]$MaxCost = 0
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot '.venv\Scripts\python.exe'
$requirementsPath = Join-Path $repoRoot 'src\architecture_validation\requirements.lock.txt'
$oldPythonPath = $env:PYTHONPATH
try {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        if ($Action -in @('stop','status')) {
            Write-Host 'DeerMind is not installed. Run .\deermind.cmd start first.'
            exit 0
        }
        Write-Host 'Preparing the local Python environment (first launch only)...'
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3 -m venv (Join-Path $repoRoot '.venv')
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv (Join-Path $repoRoot '.venv')
        } else {
            throw 'Python 3.11+ is required. Install Python, then run this command again.'
        }
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create .venv.' }
    }
    if ($Action -in @('start','setup')) {
        $dependencyCheck = @'
import importlib.metadata, pathlib, sys
assert sys.version_info >= (3,11), 'Python 3.11+ required'
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    name, version = line.split('==')
    try: installed = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: sys.exit(1)
    if installed != version: sys.exit(1)
'@
        & $pythonPath -c $dependencyCheck $requirementsPath
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Installing pinned dependencies (first launch or dependency change)...'
            & $pythonPath -m pip install -r $requirementsPath
            if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network and retry.' }
        }
        if ($Action -eq 'setup') {
            Write-Host 'DeerMind is ready. Run .\deermind.cmd start.'
            exit 0
        }
    }
    $env:PYTHONPATH = Join-Path $repoRoot 'src'
    $launchArgs = @('-X','utf8','-m','architecture_validation.launcher',$Action,'--name',$Name)
    if ($Action -eq 'start') {
        if ($Mode) { $launchArgs += @('--mode',$Mode) }
        if ($PSBoundParameters.ContainsKey('Port')) { $launchArgs += @('--port',[string]$Port) }
        if ($NewSession) { $launchArgs += '--new-session' }
        if ($NoBrowser) { $launchArgs += '--no-browser' }
        foreach ($field in @('Quantity','Total','Target','Noun')) {
            if ($PSBoundParameters.ContainsKey($field)) {
                $launchArgs += @('--'+$field.ToLower(),[string](Get-Variable -Name $field -ValueOnly))
            }
        }
        if ($MaxCalls -gt 0) { $launchArgs += @('--max-calls',[string]$MaxCalls) }
        if ($MaxCost -gt 0) { $launchArgs += @('--max-cost',$MaxCost.ToString([Globalization.CultureInfo]::InvariantCulture)) }
    }
    & $pythonPath @launchArgs
    exit $LASTEXITCODE
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    $env:PYTHONPATH = $oldPythonPath
}

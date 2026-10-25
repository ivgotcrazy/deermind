[CmdletBinding()]
param(
    [Parameter(Position=0)][ValidateSet('start','stop','status','setup','restart')][string]$Action = 'start',
    [ValidateSet('student','parent','admin')][string]$Role = 'student',
    [ValidateRange(1024,65535)][int]$Port = 5181,
    [switch]$NoBrowser
)
$entry = Join-Path (Split-Path -Parent $PSScriptRoot) 'src\mvp_prototype\scripts\prototype.ps1'
& $entry -Action $Action -Role $Role -Port $Port -NoBrowser:$NoBrowser

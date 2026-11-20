$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv/Scripts/python.exe'
$Manage = Join-Path $ProjectRoot 'manage.py'
$Runtime = Join-Path $ProjectRoot 'runtime'
function Require-Python {
    if (-not (Test-Path -LiteralPath $Python)) { throw 'Run scripts/setup.ps1 first.' }
}
function Use-Profile([string]$Profile) {
    $env:OML_ENV_FILE = Join-Path $ProjectRoot "security/$Profile.env"
    if (-not (Test-Path -LiteralPath $env:OML_ENV_FILE)) { throw "Missing security/$Profile.env. Follow the setup guide." }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
}
function Get-TrackedServerProcess($State) {
    # PID alone is not enough: reject another project or a reused process ID.
    if (-not $State.root -or [IO.Path]::GetFullPath($State.root) -ne [IO.Path]::GetFullPath($ProjectRoot)) {
        throw 'Server state belongs to another project. Refusing to stop or reuse it.'
    }
    if (-not $State.pid -or -not $State.startTicks) { throw 'Invalid runtime/service.json.' }
    $tracked = Get-Process -Id $State.pid -ErrorAction SilentlyContinue
    if (-not $tracked) { return $null }
    if ($tracked.StartTime.ToUniversalTime().Ticks.ToString() -ne $State.startTicks) {
        throw 'PID was reused. Refusing to stop or reuse an unrelated process.'
    }
    # Same-user Process.Path works without WMI/CIM permissions or administrator rights.
    if (-not $tracked.Path -or [IO.Path]::GetFullPath($tracked.Path) -ne [IO.Path]::GetFullPath($Python)) {
        throw 'Tracked process is not this project Python. Refusing to stop or reuse it.'
    }
    return $tracked
}

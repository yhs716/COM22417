# Workspace terminal entry point. Runs in the new terminal process itself.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$venvRoot = Join-Path $ProjectRoot '.venv'
$venvScripts = Join-Path $venvRoot 'Scripts'
if (Test-Path -LiteralPath (Join-Path $venvScripts 'python.exe')) {
    # Python 3.12 Activate.ps1 treats brackets in a folder as wildcards.
    # Activate directly so every valid project folder follows the same rules.
    if (Test-Path Function:deactivate) { deactivate }
    $global:OMLPreviousPath = $env:PATH
    $global:OMLPreviousPythonHome = $env:PYTHONHOME
    $global:OMLPreviousPrompt = (Get-Command prompt).ScriptBlock
    function global:deactivate {
        $env:PATH = $global:OMLPreviousPath
        if ($null -ne $global:OMLPreviousPythonHome) { $env:PYTHONHOME = $global:OMLPreviousPythonHome }
        else { Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue }
        Remove-Item Env:VIRTUAL_ENV,Env:VIRTUAL_ENV_PROMPT -ErrorAction SilentlyContinue
        Set-Item Function:global:prompt -Value $global:OMLPreviousPrompt
        Remove-Variable OMLPreviousPath,OMLPreviousPythonHome,OMLPreviousPrompt -Scope Global
        Remove-Item Function:deactivate
    }
    Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
    $env:VIRTUAL_ENV = $venvRoot
    $env:VIRTUAL_ENV_PROMPT = '.venv'
    $env:PATH = $venvScripts + [IO.Path]::PathSeparator + $env:PATH
    function global:prompt { '(.venv) ' + (& $global:OMLPreviousPrompt) }
    Write-Host 'OML project environment is active.' -ForegroundColor Green
    python --version
    python -c "import sys; print('Python:',sys.executable); print('venv:',sys.prefix != sys.base_prefix)"
    if ($LASTEXITCODE -ne 0) { throw 'Environment activation check failed.' }
} else {
    Write-Host 'First run: powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1' -ForegroundColor Yellow
    Write-Host 'Then close this terminal and open a new OML (.venv) terminal.'
}

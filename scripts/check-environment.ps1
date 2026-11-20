. "$PSScriptRoot/common.ps1"
Write-Host "Project: $ProjectRoot"
Write-Host "`nPython commands on PATH (these may differ from the project interpreter):"
Get-Command python -All -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (Get-Command python -ErrorAction SilentlyContinue) { python --version }
if (Get-Command py -ErrorAction SilentlyContinue) { py -0p }
Write-Host "`nProject interpreter:"
if (Test-Path -LiteralPath $Python) {
    & $Python -c "import sys,struct; print(sys.executable); print(sys.version); print('venv:',sys.prefix != sys.base_prefix); print('bits:',struct.calcsize('P')*8)"
    & $Python -m pip check
} else { Write-Warning 'Project .venv is missing. Run scripts/setup.ps1.' }
Write-Host "`nVS Code extensions:"
if (Get-Command code -ErrorAction SilentlyContinue) {
    $installed = @(code --list-extensions --show-versions)
    if ($LASTEXITCODE -ne 0) { throw 'VS Code extension inventory failed.' }
    $required = @('ms-python.python', 'ms-python.vscode-pylance', 'ms-python.debugpy')
    foreach ($extension in $required) {
        $match = @($installed | Where-Object { $_ -match ('(?i)^' + [regex]::Escape($extension) + '@') })
        if ($match.Count) { Write-Host "OK: $($match[0])" }
        else { Write-Host "MISSING: code --install-extension $extension" -ForegroundColor Yellow }
    }
} else { Write-Warning 'code is not on PATH. Open VS Code Extensions (Ctrl+Shift+X), then search @installed.' }
Write-Host "`nThis check does not read DB passwords or change installed software."

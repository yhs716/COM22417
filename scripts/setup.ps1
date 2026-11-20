param([string]$PythonExe='', [string]$AssetsPath='', [switch]$InstallExtensions)
. "$PSScriptRoot/common.ps1"
# Optional relative paths follow the project, not the terminal's current folder.
if ($PythonExe -and -not [IO.Path]::IsPathRooted($PythonExe)) {
    $PythonExe=Join-Path $ProjectRoot $PythonExe
}
function Test-Python([string]$Executable) {
    try {
        $result=& $Executable -I -c "import sys,struct; print((3,12)<=sys.version_info[:2]<=(3,14) and struct.calcsize('P')==8)" 2>$null
        return $result -eq 'True'
    } catch { return $false }
}
if (-not (Test-Path -LiteralPath $Python)) {
    $candidates=@($PythonExe)
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($minor in @('3.14','3.13','3.12')) {
            try {
                $found=& py "-$minor" -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0) { $candidates+=$found }
            } catch { continue }
        }
    }
    foreach ($minor in @('314','313','312')) {
        $candidates+=@("$env:LOCALAPPDATA/Programs/Python/Python$minor/python.exe","C:/Program Files/Python$minor/python.exe")
    }
    $command=Get-Command python -ErrorAction SilentlyContinue
    if ($command) { $candidates+=$command.Source }
    $selected=$null
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate) -and (Test-Python $candidate)) { $selected=$candidate; break }
    }
    if (-not $selected) { throw 'Install Python 3.12-3.14 x64 first. See COM22417_과제설명및평가.html.' }
    & $selected -I -m venv (Join-Path $ProjectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
if (-not (Test-Python $Python)) { throw 'Python 3.12-3.14 x64 is required.' }
# Installation must target this project's venv, even when another environment is active.
# -I ignores PYTHONHOME/PYTHONPATH; pip --isolated ignores user options/environment variables.
& $Python -I -c "import sys,pathlib; expected=pathlib.Path(sys.argv[1]).resolve(); assert sys.prefix != sys.base_prefix and pathlib.Path(sys.prefix).resolve()==expected, 'Refusing installation outside project .venv'" (Join-Path $ProjectRoot '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Project venv check failed. No packages were installed.' }
$pipArgs=@('-I','-m','pip','--isolated','--require-virtualenv','install','--disable-pip-version-check','-r',(Join-Path $ProjectRoot 'requirements.txt'))
if ($AssetsPath) {
    if (-not [IO.Path]::IsPathRooted($AssetsPath)) { $AssetsPath=Join-Path $ProjectRoot $AssetsPath }
    $assetRoot=(Resolve-Path -LiteralPath $AssetsPath).Path
    $wheelPath=Join-Path $assetRoot 'wheels'
    if (-not (Test-Path -LiteralPath $wheelPath)) { $wheelPath=$assetRoot }
    $pipArgs+=@('--no-index','--find-links',$wheelPath)
}
& $Python @pipArgs
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed. Check network or external wheels.' }
& $Python -I -m pip --isolated --require-virtualenv check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
$studentSettings=Join-Path $ProjectRoot 'security/student.env'
if (-not (Test-Path -LiteralPath $studentSettings)) { Copy-Item -LiteralPath (Join-Path $ProjectRoot 'security/student.env.example') -Destination $studentSettings }
$roster=Join-Path $ProjectRoot 'security/students.json'
if (-not (Test-Path -LiteralPath $roster)) { [IO.File]::WriteAllText($roster,'[]'+[Environment]::NewLine,[Text.UTF8Encoding]::new($false)) }
if ($InstallExtensions) {
    if (Get-Command code -ErrorAction SilentlyContinue) {
        $installed=@(& code --list-extensions)
        foreach ($extension in @('ms-python.python','ms-python.vscode-pylance','ms-python.debugpy')) {
            if ($installed -notcontains $extension) { & code --install-extension $extension; if ($LASTEXITCODE -ne 0) { throw "Extension installation failed: $extension" } }
        }
    } else { Write-Host 'Check Python, Pylance and Python Debugger in the VS Code Extensions panel (Ctrl+Shift+X).' }
}
Write-Host 'Ready. Configure Wallet/DSN in security/student.env; web login fills DB_USER and DB_PASSWORD.'
Write-Host 'Run scripts/start.ps1, then use Login to enter student ID, name and issued DB password.'
# setup.ps1 is normally invoked in the VS Code PowerShell terminal itself.
# Activate that session now; selecting a VS Code interpreter alone does not activate an existing terminal.
. "$PSScriptRoot/terminal-init.ps1"

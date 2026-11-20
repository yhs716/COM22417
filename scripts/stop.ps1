. "$PSScriptRoot/common.ps1"
$statePath = Join-Path $Runtime 'service.json'
if (-not (Test-Path -LiteralPath $statePath)) { Write-Host 'No tracked server.'; return }
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$process = Get-TrackedServerProcess $state
if ($process) {
    Stop-Process -InputObject $process -ErrorAction Stop
    if (-not $process.WaitForExit(5000)) { throw 'Server did not stop within 5 seconds.' }
    Write-Host 'OML Studio stopped.'
} else { Write-Host 'Tracked server is already stopped.' }
Remove-Item -LiteralPath $statePath

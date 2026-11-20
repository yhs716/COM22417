param([ValidateSet('student','teacher')][string]$Profile='student', [ValidateRange(1024,65535)][int]$Port=22417)
$portWasSpecified = $PSBoundParameters.ContainsKey('Port')
. "$PSScriptRoot/common.ps1"
Require-Python
Use-Profile $Profile
New-Item -ItemType Directory -Path $Runtime -Force | Out-Null
$statePath = Join-Path $Runtime 'service.json'
if (Test-Path -LiteralPath $statePath) {
    $old = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $running = Get-TrackedServerProcess $old
    if ($running) {
        if (($portWasSpecified -and $old.port -ne $Port) -or $old.profile -ne $Profile) {
            throw "Server already runs on port $($old.port) ($($old.profile)). Use restart.ps1 -Profile $Profile -Port $Port to change it."
        }
        Write-Host "Already running: http://127.0.0.1:$($old.port)"
        return
    }
}
# 기본 포트가 이미 사용 중이어도 다른 프로그램을 종료하지 않고 빈 포트를 찾습니다.
# -Port도 우선 시도할 번호이며, 선택된 실제 포트는 service.json에 저장합니다.
$requestedPort = $Port
$selectedPort = $null
for ($candidate=$requestedPort; $candidate -le [Math]::Min(65535,$requestedPort+99); $candidate++) {
    $probe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $candidate)
    $probe.Server.ExclusiveAddressUse = $true
    try { $probe.Start(); $selectedPort=$candidate; break }
    catch [System.Net.Sockets.SocketException] { continue }
    finally { $probe.Stop() }
}
if ($null -eq $selectedPort) {
    # 연속된 번호가 모두 막혀 있으면 OS에서 빈 포트 하나를 배정받습니다.
    $probe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
    $probe.Server.ExclusiveAddressUse = $true
    try { $probe.Start(); $selectedPort=$probe.LocalEndpoint.Port }
    finally { $probe.Stop() }
}
$Port = [int]$selectedPort
if ($Port -ne $requestedPort) {
    Write-Host "Port $requestedPort is unavailable. Using free port $Port. Existing servers were not stopped."
}
$argsList = @(('"' + $Manage + '"'), 'serve', '--port', $Port.ToString(), '--log-files')
# Python resolves files against its source location. Avoid PowerShell 5 wildcard
# interpretation of brackets in WorkingDirectory and redirection paths.
$proc = Start-Process -FilePath $Python -ArgumentList $argsList -WindowStyle Hidden -PassThru
$state = @{pid=$proc.Id; startTicks=$proc.StartTime.ToUniversalTime().Ticks.ToString(); port=$Port; profile=$Profile; root=$ProjectRoot}
$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
$ready=$false
for ($attempt=0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    $proc.Refresh()
    if ($proc.HasExited) { throw 'Web process exited. See runtime/server.err.log.' }
    try { $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 2; if ($response.StatusCode -eq 200) { $ready=$true; break } } catch {}
}
if (-not $ready) { throw 'Server readiness timed out. See runtime/server.err.log.' }
Write-Host "OML Studio is ready: http://127.0.0.1:$Port"
Write-Host "Profile: $Profile. Stop with scripts/stop.ps1."

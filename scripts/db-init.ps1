param([ValidateSet('student','teacher')][string]$Profile='student')
. "$PSScriptRoot/common.ps1"
Require-Python
Use-Profile $Profile
Write-Host 'Applying basic tables, OML_BASIC_RUN procedure and DB comments. Existing table rows are preserved.'
Write-Host 'This applies SQL definitions, not model training. Mission/creative SQL must be executed in your DB tool.'
& $Python $Manage check
if ($LASTEXITCODE -ne 0) { throw 'Connection check failed.' }
& $Python $Manage init
if ($LASTEXITCODE -ne 0) { throw 'Schema initialization failed.' }

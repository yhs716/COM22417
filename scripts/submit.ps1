param([Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]{4,20}$')][string]$StudentId)
. "$PSScriptRoot/common.ps1"
Require-Python
& $Python (Join-Path $PSScriptRoot 'package_submission.py') --student-id $StudentId
if ($LASTEXITCODE -ne 0) { throw 'Submission packaging failed. Check Python/SQL source, report and PPT, then review the message above.' }

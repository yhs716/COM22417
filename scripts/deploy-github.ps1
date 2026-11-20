param(
    [string]$Repository = '',
    [string]$Branch = 'main',
    [string]$Message = 'Update my OML assignment',
    [string]$AuthorName = '',
    [string]$AuthorEmail = '',
    [switch]$Prepare,
    [switch]$Push
)
# Student publication: always specify your own repository. No default remote.
. "$PSScriptRoot/common.ps1"
if (-not $Repository) { throw 'Specify your own GitHub HTTPS URL with -Repository. See the GitHub section in the setup guide.' }
if ($Prepare -and $Push) { throw 'Choose -Prepare or -Push, not both.' }
Require-Python
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$publishArgs = @((Join-Path $PSScriptRoot 'git_publish.py'), '--repository', $Repository, '--branch', $Branch, '--message', $Message)
if ($AuthorName) { $publishArgs += @('--author-name', $AuthorName) }
if ($AuthorEmail) { $publishArgs += @('--author-email', $AuthorEmail) }
if ($Prepare) { $publishArgs += '--prepare' }
if ($Push) { $publishArgs += '--push' }
& $Python @publishArgs
if ($LASTEXITCODE -ne 0) { throw 'Student Git publication stopped. Check the message above.' }

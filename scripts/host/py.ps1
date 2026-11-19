# Like run.ps1, for any evalkit module that calls the Claude API (for example the judge):
# loads the API key from the user's environment without printing it, then runs
# `python -m <module> <args>` from this checkout.
#
#   powershell -ExecutionPolicy Bypass -File scripts\host\py.ps1 evalkit.judge --run main-rescored
param([Parameter(Mandatory)][string]$Module, [Parameter(ValueFromRemainingArguments)][string[]]$Rest)
$env:ANTHROPIC_API_KEY = [Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY', 'User')
if (-not $env:ANTHROPIC_API_KEY) { throw 'Set the ANTHROPIC_API_KEY user environment variable first.' }
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location (Split-Path (Split-Path $PSScriptRoot))
& 'D:\eval-vms\venv\Scripts\python.exe' -m $Module @Rest
exit $LASTEXITCODE

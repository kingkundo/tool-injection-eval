# Runs the harness from D:\eval-vms\harness with the API key from the user's environment
# variable, read from the registry so a process started before the variable was set (such as
# Dashcat Agent) still finds it. The key is never printed. Arguments go to evalkit.run, e.g.
#
#   powershell -ExecutionPolicy Bypass -File scripts\host\run.ps1 --run pilot --limit 50 --budget 35
param([Parameter(ValueFromRemainingArguments)][string[]]$Rest)
$env:ANTHROPIC_API_KEY = [Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY', 'User')
if (-not $env:ANTHROPIC_API_KEY) { throw 'Set the ANTHROPIC_API_KEY user environment variable first.' }
$env:PYTHONUNBUFFERED = '1'
Set-Location (Split-Path (Split-Path $PSScriptRoot))
& 'D:\eval-vms\venv\Scripts\python.exe' -m evalkit.run @Rest
exit $LASTEXITCODE

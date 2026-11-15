# Removes everything the eval put on a Windows host, after the results are saved. Run it in
# an elevated PowerShell on the host:
#
#   powershell -ExecutionPolicy Bypass -File cleanup-host.ps1 -Root D:\eval-vms -Keep D:\eval-results
#
# It copies results\ to -Keep first, then deletes the VMs and their disks, the ISOs, the
# harness checkout and its Python environment, the eval ssh key and its known_hosts lines, and
# the ANTHROPIC_API_KEY user variable; with -Uninstall it also removes VirtualBox and Python
# 3.12. It never touches Dashcat itself: remove the eval nodes in Dashcat Dashboard and sign
# the bridge out by hand.
param(
    [string]$Root = 'D:\eval-vms',
    [string]$Keep = 'D:\eval-results',
    [string[]]$Vms = @('eval-linux', 'eval-windows'),
    [switch]$Uninstall
)
$ErrorActionPreference = 'Continue'
$vbm = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'

$results = Join-Path $Root 'harness\results'
if (Test-Path $results) {
    New-Item -ItemType Directory -Force -Path $Keep | Out-Null
    Copy-Item -Recurse -Force "$results\*" $Keep
    "Results copied to $Keep"
}

if (Test-Path $vbm) {
    foreach ($vm in $Vms) {
        & $vbm controlvm $vm poweroff 2>$null | Out-Null
        Start-Sleep -Seconds 3
        & $vbm unregistervm $vm --delete-all 2>$null
        "Deleted VM $vm"
    }
}

# Remove the eval VMs' lines from every profile's ssh files, and the key made for them.
foreach ($profile in Get-ChildItem 'C:\Users' -Directory) {
    $ssh = Join-Path $profile.FullName '.ssh'
    foreach ($file in 'known_hosts', 'config') {
        $path = Join-Path $ssh $file
        if (Test-Path $path) {
            $text = Get-Content -Raw $path
            $kept = ($text -split "(?m)^(?=Host )" | Where-Object { $_ -notmatch '^Host eval-' }) -join ''
            if ($file -eq 'known_hosts') { $kept = (Get-Content $path | Where-Object { $_ -notmatch '^(eval-|192\.168\.56\.)' }) -join "`n" }
            Set-Content -NoNewline $path $kept
        }
    }
    Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $ssh 'eval_ed25519'), (Join-Path $ssh 'eval_ed25519.pub')
}

[Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', $null, 'User')
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Root
"Removed $Root"

if ($Uninstall) {
    $keys = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    $apps = Get-ItemProperty $keys -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match '^(Oracle VirtualBox|Python 3\.12\.\d+ \(64-bit\))' -and $_.PSChildName -match '^\{' }
    foreach ($app in $apps) {
        "Uninstalling $($app.DisplayName)"
        Start-Process msiexec.exe -ArgumentList "/x $($app.PSChildName) /qn /norestart" -Wait
    }
    $bundle = Get-ItemProperty $keys -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match '^Python 3\.12\.\d+ \(64-bit\)$' -and $_.QuietUninstallString }
    foreach ($b in $bundle) { cmd /c $b.QuietUninstallString }
}
'Done. In Dashcat Dashboard: remove the eval-linux and eval-windows nodes. On this PC: dashcat-bridge logout.'

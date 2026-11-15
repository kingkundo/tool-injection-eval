# Installs Dashcat Agent in a VM as the "eval" user, joined Direct mode only with the invite
# link in D:\eval-vms\invite-<os>.txt. The link goes in by file and is deleted from the VM
# afterwards, so it never shows in a command line or in chat. Administrator commands are turned
# on later, after the VM pairs with the eval bridge (the admin service trusts only the bridges
# paired when it is installed). Guest commands avoid double quotes: PowerShell 5.1 mangles them
# when it passes arguments to VBoxManage.
param([Parameter(Mandatory)][ValidateSet('eval-linux', 'eval-windows')][string]$Name)
$ErrorActionPreference = 'Stop'
$vbm = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
$root = 'D:\eval-vms'
$pw = Join-Path $root 'vm-password.txt'
$auth = @('--username', 'eval', '--passwordfile', $pw)

function GuestRun([string]$exe, [string[]]$guestArgs) {
    & $vbm guestcontrol $Name run @auth --timeout 1200000 --wait-stdout --wait-stderr --exe $exe -- @guestArgs
    if ($LASTEXITCODE -ne 0) { throw "$exe failed in $Name with exit code $LASTEXITCODE" }
}

if ($Name -eq 'eval-linux') {
    # The installer calls sudo with no terminal, so it gets the password from a short-lived
    # askpass helper (sudo uses one without a terminal only when DISPLAY is set); the helper
    # and the password copy are deleted whatever happens.
    & $vbm guestcontrol $Name copyto @auth --target-directory /home/eval/ "$root\invite-linux.txt" $pw
    $sh = 'cd /home/eval; mv vm-password.txt .evalpw; chmod 600 .evalpw invite-linux.txt; ' +
          'printf ''#!/bin/sh\ncat /home/eval/.evalpw\n'' > .askpass; chmod 700 .askpass; ' +
          'trap ''rm -f /home/eval/.evalpw /home/eval/.askpass /home/eval/invite-linux.txt'' EXIT; ' +
          'export SUDO_ASKPASS=/home/eval/.askpass DISPLAY=:0; ' +
          'export DASHCAT_INVITE=$(tr -d \\r\\n < invite-linux.txt); rm -f invite-linux.txt; ' +
          'export DASHCAT_HOSTED=deny DASHCAT_ADMIN=deny DASHCAT_YES=1; ' +
          'curl -fsSL https://app.dashcat.ai/install.sh -o /tmp/dashcat-install.sh && sh /tmp/dashcat-install.sh'
    GuestRun '/bin/bash' @('-c', $sh)
} else {
    & $vbm guestcontrol $Name copyto @auth --target-directory 'C:\Users\eval\' "$root\invite-windows.txt"
    $ps = '$env:DASHCAT_INVITE = (Get-Content -Raw C:\Users\eval\invite-windows.txt).Trim(); Remove-Item C:\Users\eval\invite-windows.txt; ' +
          '$env:DASHCAT_HOSTED = ''deny''; $env:DASHCAT_ADMIN = ''deny''; $env:DASHCAT_YES = ''1''; irm https://app.dashcat.ai/install.ps1 | iex'
    GuestRun 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $ps)
}

# Runs the repo's setup script inside a freshly installed VM, then gives this PC's user ssh
# access to it as "eval" with a key made only for the eval, and an ssh config entry for the
# VM's fixed host-only address. Guest command lines avoid double quotes: Windows PowerShell 5.1
# mangles them when passing arguments to native programs.
#
# Linux: the setup script runs through Guest Additions with sudo; run static-ip-linux.ps1 next.
# Windows: Guest Additions commands are not elevated, so windows-elevated.ps1 is started from
# the VM's desktop (start-elevated.ps1) and sets the fixed address itself.
param([Parameter(Mandatory)][ValidateSet('eval-linux', 'eval-windows')][string]$Name)
$ErrorActionPreference = 'Stop'
$vbm = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
$root = 'D:\eval-vms'
$pw = Join-Path $root 'vm-password.txt'
$repo = Join-Path $root 'harness\scripts'
$sshDir = Join-Path $env:USERPROFILE '.ssh'
$key = Join-Path $sshDir 'eval_ed25519'
$auth = @('--username', 'eval', '--passwordfile', $pw)

New-Item -ItemType Directory -Force $sshDir | Out-Null
if (-not (Test-Path $key)) { & 'C:\Program Files\Git\usr\bin\ssh-keygen.exe' -q -t ed25519 -N '' -C eval-harness -f ($key -replace '\\', '/') }

# The guest numbers its adapters in its own order (Windows puts the host-only one first), so
# take whichever address is on the host-only network.
$ip = (& $vbm guestproperty enumerate $Name) | Select-String "V4/IP\s+=\s+'(192\.168\.56\.\d+)'" |
    Select-Object -First 1 | ForEach-Object { $_.Matches[0].Groups[1].Value }
if (-not $ip) { throw "$Name has no host-only address yet" }

function GuestRun([string]$exe, [string[]]$guestArgs, [int]$timeoutMs = 1800000) {
    & $vbm guestcontrol $Name run @auth --timeout $timeoutMs --wait-stdout --wait-stderr --exe $exe -- @guestArgs
    if ($LASTEXITCODE -ne 0) { throw "$exe failed in $Name with exit code $LASTEXITCODE" }
}

if ($Name -eq 'eval-linux') {
    & $vbm guestcontrol $Name copyto @auth --target-directory /home/eval/ "$repo\setup-linux-vm.sh" "$key.pub" $pw
    GuestRun '/bin/bash' @('-c', 'cd /home/eval && sudo -S bash setup-linux-vm.sh < vm-password.txt; s=$?; rm -f vm-password.txt; exit $s')
    GuestRun '/bin/bash' @('-c', 'mkdir -p ~/.ssh && cat ~/eval_ed25519.pub >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys && rm ~/eval_ed25519.pub')
} else {
    & $vbm guestcontrol $Name mkdir @auth --parents 'C:\evalsetup'
    & $vbm guestcontrol $Name copyto @auth --target-directory 'C:\evalsetup\' "$repo\setup-windows-vm.ps1" "$repo\host\windows-elevated.ps1" "$key.pub" $pw
    & (Join-Path $PSScriptRoot 'start-elevated.ps1') -GuestScript 'C:\evalsetup\windows-elevated.ps1'
    # Installing the OpenSSH server alone can take 15 minutes under Hyper-V.
    $deadline = (Get-Date).AddMinutes(45)
    do {
        Start-Sleep 30
        $log = (& $vbm guestcontrol $Name run @auth --wait-stdout --exe 'C:\Windows\System32\cmd.exe' -- /c type C:\evalsetup-log.txt 2>$null) -join "`n"
    } until ($log -match '(?m)^(DONE|FAILED.*)$' -or (Get-Date) -gt $deadline)
    if ($Matches[1] -ne 'DONE') { throw "setup in $Name did not finish: $($Matches[1])" }
    $ip = '192.168.56.11'
}

# An ssh config entry so the harness hooks can say "ssh eval-linux".
$config = Join-Path $sshDir 'config'
$entry = "Host $Name`n    HostName $ip`n    User eval`n    IdentityFile ~/.ssh/eval_ed25519`n    IdentitiesOnly yes`n    StrictHostKeyChecking accept-new`n    LogLevel ERROR`n"
$text = if (Test-Path $config) { [IO.File]::ReadAllText($config) } else { '' }
if ($text -notmatch "(?m)^Host $Name\s*$") { [IO.File]::AppendAllText($config, "`n$entry") }
& 'C:\Program Files\Git\usr\bin\ssh.exe' $Name 'echo ssh ok'
if ($Name -eq 'eval-windows') { & 'C:\Program Files\Git\usr\bin\ssh.exe' $Name 'del C:\evalsetup-log.txt C:\vboxpostinstall.log' }

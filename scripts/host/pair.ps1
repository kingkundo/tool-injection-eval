# Pairs a VM's Dashcat Agent with this PC's bridge over the host-only network, then turns on
# administrator commands (the admin service trusts the bridges paired when it is installed).
# The VMs have fixed host-only addresses.
#
# Windows: when Dashcat Agent first listens, Windows Firewall asks whether to allow it. Nobody
# answers in a headless VM, and an unanswered prompt leaves Block rules that override
# windows-elevated.ps1's allow rule, so they are removed first. Clear any pop-ups left on the
# VM's screen (check with `dashcat-bridge screenshot`) before taking the snapshot.
param([Parameter(Mandatory)][ValidateSet('eval-linux', 'eval-windows')][string]$Name)
$ErrorActionPreference = 'Stop'
$ssh = 'C:\Program Files\Git\usr\bin\ssh.exe'
$ip = @{ 'eval-linux' = '192.168.56.10'; 'eval-windows' = '192.168.56.11' }[$Name]

if ($Name -eq 'eval-windows') {
    & $ssh $Name 'powershell -NoProfile -Command Get-NetFirewallRule -DisplayName dashcat-agent* -ErrorAction SilentlyContinue ^| Where-Object Action -eq Block ^| Remove-NetFirewallRule'
}
$out = (& $ssh $Name 'dashcat-agent pair') -join "`n"
if ($out -notmatch 'Pairing code: (\S+)') { throw "no pairing code from $Name`n$out" }
$code = $Matches[1]
$ErrorActionPreference = 'Continue'
dashcat-bridge nodes remove $Name 2>$null | Out-Null
$ErrorActionPreference = 'Stop'
dashcat-bridge nodes add $Name $ip --code $code
if ($LASTEXITCODE -ne 0) { throw "pairing $Name failed" }
dashcat-bridge info $Name

if ($Name -eq 'eval-linux') {
    Get-Content -Raw 'D:\eval-vms\vm-password.txt' |
        & $ssh $Name 'sudo -S dashcat-admin install --agent-config /home/eval/.config/dashcat/agent.toml'
} else {
    & $ssh $Name 'dashcat-agent admin enable'
}
if ($LASTEXITCODE -ne 0) { throw "turning on administrator commands failed on $Name" }
& $ssh $Name 'dashcat-agent bridges list'

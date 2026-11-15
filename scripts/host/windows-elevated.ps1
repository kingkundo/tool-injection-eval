# Runs inside eval-windows, elevated, started from its desktop: commands VirtualBox runs in the
# guest get a non-elevated token (UAC), so provision.ps1 copies this in and start-elevated.ps1
# starts it through the Run box and accepts the UAC prompt with the keyboard. Expects
# C:\evalsetup to hold setup-windows-vm.ps1, eval_ed25519.pub and vm-password.txt. Logs to
# C:\evalsetup-log.txt (delete it before the snapshot) and ends with DONE or FAILED.
$ErrorActionPreference = 'Stop'
Start-Transcript -Path C:\evalsetup-log.txt -Force | Out-Null
try {
    & C:\evalsetup\setup-windows-vm.ps1

    Get-Content C:\evalsetup\eval_ed25519.pub | Add-Content C:\ProgramData\ssh\administrators_authorized_keys
    icacls C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r /grant Administrators:F /grant SYSTEM:F | Out-Null

    # Automatic sign-in as eval, so a restored snapshot always has a desktop session.
    $pw = (Get-Content -Raw C:\evalsetup\vm-password.txt).Trim()
    $winlogon = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
    Set-ItemProperty $winlogon AutoAdminLogon '1'
    Set-ItemProperty $winlogon DefaultUserName 'eval'
    Set-ItemProperty $winlogon DefaultDomainName 'EVAL-WINDOWS'
    Set-ItemProperty $winlogon DefaultPassword $pw
    Remove-ItemProperty $winlogon AutoLogonCount -ErrorAction SilentlyContinue

    # No sleep, screen-off or lock: screenshots must show the desktop.
    powercfg /change monitor-timeout-ac 0
    powercfg /change standby-timeout-ac 0
    New-Item -Force 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization' | Out-Null
    Set-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization' NoLockScreen 1 -Type DWord

    # A fixed address on the host-only adapter (the one not on VirtualBox's NAT, 10.0.2.x).
    $nat = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '10.0.2.*' }).InterfaceIndex
    $nic = Get-NetAdapter -Physical | Where-Object { $_.ifIndex -ne $nat } | Select-Object -First 1
    Set-NetIPInterface -InterfaceIndex $nic.ifIndex -Dhcp Disabled
    Get-NetIPAddress -InterfaceIndex $nic.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
    New-NetIPAddress -InterfaceIndex $nic.ifIndex -IPAddress 192.168.56.11 -PrefixLength 24 | Out-Null

    # With NAT off the host-only network has no gateway, so Windows calls it unidentified and
    # Public. Treat unidentified networks as Private, and let ssh, ping and Dashcat Agent in from
    # the host-only subnet whatever the profile.
    $sig = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\CurrentVersion\NetworkList\Signatures\010103000F0000F0010000000F0000F0'
    New-Item -Force $sig | Out-Null
    Set-ItemProperty $sig Category 1 -Type DWord
    foreach ($r in @(@{Name = 'eval-dashcat-agent'; Port = 7420 }, @{Name = 'eval-ssh'; Port = 22 })) {
        Remove-NetFirewallRule -Name $r.Name -ErrorAction SilentlyContinue
        New-NetFirewallRule -Name $r.Name -DisplayName $r.Name -Direction Inbound -Protocol TCP -LocalPort $r.Port `
            -Profile Any -RemoteAddress 192.168.56.0/24 -Action Allow | Out-Null
    }
    Remove-NetFirewallRule -Name eval-ping -ErrorAction SilentlyContinue
    New-NetFirewallRule -Name eval-ping -DisplayName eval-ping -Direction Inbound -Protocol ICMPv4 -IcmpType 8 `
        -Profile Any -RemoteAddress 192.168.56.0/24 -Action Allow | Out-Null
    'DONE'
} catch {
    "FAILED: $_"
} finally {
    Remove-Item -Recurse -Force C:\evalsetup -ErrorAction SilentlyContinue
    Stop-Transcript | Out-Null
}

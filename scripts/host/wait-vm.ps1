# Waits until a VM reports a host-only IP through Guest Additions (the install has finished and
# the guest service runs). The property can be stale after a reboot: check ssh too.
param([string]$Name, [int]$Minutes = 60)
$vbm = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
$deadline = (Get-Date).AddMinutes($Minutes)
while ((Get-Date) -lt $deadline) {
    $ip = & $vbm guestproperty get $Name '/VirtualBox/GuestInfo/Net/1/V4/IP' 2>$null
    $users = & $vbm guestproperty get $Name '/VirtualBox/GuestInfo/OS/LoggedInUsers' 2>$null
    if ($ip -match 'Value: (\S+)') {
        "$Name ready: host-only IP $($Matches[1]); $users"
        exit 0
    }
    Start-Sleep -Seconds 30
}
"$Name not ready after $Minutes minutes"
exit 1

# Gives eval-linux a fixed host-only address (192.168.56.10), so ssh and the bridge never chase
# a DHCP change, and points this PC's ssh config at it.
$ErrorActionPreference = 'Stop'
$ssh = 'C:\Program Files\Git\usr\bin\ssh.exe'
$config = Join-Path $env:USERPROFILE '.ssh\config'
$vbm = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
function SetHost($ip) {
    $t = [IO.File]::ReadAllText($config)
    $t = [regex]::Replace($t, '(?ms)(^Host eval-linux\s*\n\s*HostName )\S+', "`${1}$ip")
    [IO.File]::WriteAllText($config, $t)
}
$current = ((& $vbm guestproperty get eval-linux '/VirtualBox/GuestInfo/Net/1/V4/IP') -replace 'Value: ', '').Trim()
SetHost $current
$plan = @'
network:
  version: 2
  ethernets:
    enp0s8:
      dhcp4: false
      addresses: [192.168.56.10/24]
'@
$plan | & $ssh eval-linux 'cat > /tmp/60-eval.yaml'
Get-Content -Raw 'D:\eval-vms\vm-password.txt' |
    & $ssh eval-linux "sudo -S -p '' sh -c 'install -m 600 /tmp/60-eval.yaml /etc/netplan/60-eval.yaml && (sleep 2; netplan apply) >/dev/null 2>&1 &'"
Start-Sleep -Seconds 15
SetHost '192.168.56.10'
& $ssh eval-linux 'ip -4 -o addr show enp0s8'

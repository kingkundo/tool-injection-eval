# Creates the eval-linux VM and starts an unattended Ubuntu 24.04 Server install (the Desktop
# ISO's unattended install hung twice; setup-linux-vm.sh adds the desktop). Settings that
# matter under Hyper-V (VirtualBox on the Windows hypervisor, when Memory Integrity is on):
# 1 vCPU (2 hangs at boot on the clock source) and EFI firmware (BIOS fails to boot after
# setup upgrades grub). The VM password is made once and lives only in vm-password.txt.
$ErrorActionPreference = 'Stop'
$vbm = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
$root = 'D:\eval-vms'
$pw = Join-Path $root 'vm-password.txt'
if (-not (Test-Path $pw)) {
    $chars = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'.ToCharArray()
    -join (1..20 | ForEach-Object { $chars | Get-Random }) | Set-Content -NoNewline $pw
}
# Host-only network for the harness to reach the VMs once NAT is switched off.
$hostonly = (& $vbm list hostonlyifs | Select-String '^Name:\s+(.*)$' | Select-Object -First 1)
if (-not $hostonly) { & $vbm hostonlyif create; $hostonly = (& $vbm list hostonlyifs | Select-String '^Name:\s+(.*)$' | Select-Object -First 1) }
$hostonly = $hostonly.Matches[0].Groups[1].Value.Trim()
"host-only adapter: $hostonly"

$name = 'eval-linux'
$dir = Join-Path $root $name
& $vbm createvm --name $name --ostype Ubuntu24_LTS_64 --basefolder $root --register
& $vbm modifyvm $name --memory 4096 --cpus 1 --firmware efi --vram 64 --graphicscontroller vmsvga --audio-enabled off `
    --nic1 nat --nic2 hostonly --host-only-adapter2 "$hostonly" --clipboard-mode disabled --drag-and-drop disabled
& $vbm createmedium disk --filename "$dir\$name.vdi" --size 40960 --format VDI
& $vbm storagectl $name --name SATA --add sata --controller IntelAhci --portcount 2
& $vbm storageattach $name --storagectl SATA --port 0 --device 0 --type hdd --medium "$dir\$name.vdi"
& $vbm storageattach $name --storagectl SATA --port 1 --device 0 --type dvddrive --medium emptydrive
& $vbm unattended install $name --iso "$root\iso\ubuntu-24.04.5-live-server-amd64.iso" `
    --user eval --full-user-name 'Eval' --password-file $pw --hostname eval-linux.local `
    --locale en_GB --country GB --time-zone UTC --install-additions --start-vm headless
"started $name"

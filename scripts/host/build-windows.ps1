# Creates the eval-windows VM and starts an unattended Windows 11 Enterprise Evaluation install.
# Run build-linux.ps1 first (it makes the password file and the host-only adapter). 2 vCPUs:
# with 4, setup stalled under Hyper-V. Lines mentioning the password are filtered from output.
$ErrorActionPreference = 'Stop'
$vbm = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
$root = 'D:\eval-vms'
$pw = Join-Path $root 'vm-password.txt'
$hostonly = (& $vbm list hostonlyifs | Select-String '^Name:\s+(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim()

$name = 'eval-windows'
$dir = Join-Path $root $name
& $vbm createvm --name $name --ostype Windows11_64 --basefolder $root --register
& $vbm modifyvm $name --memory 8192 --cpus 2 --vram 128 --graphicscontroller vboxsvga --audio-enabled off `
    --firmware efi --tpm-type 2.0 --chipset ich9 `
    --nic1 nat --nic2 hostonly --host-only-adapter2 "$hostonly" --clipboard-mode disabled --drag-and-drop disabled
& $vbm createmedium disk --filename "$dir\$name.vdi" --size 61440 --format VDI
& $vbm storagectl $name --name SATA --add sata --controller IntelAhci --portcount 2
& $vbm storageattach $name --storagectl SATA --port 0 --device 0 --type hdd --medium "$dir\$name.vdi"
& $vbm storageattach $name --storagectl SATA --port 1 --device 0 --type dvddrive --medium emptydrive
& $vbm unattended install $name --iso "$root\iso\win11-enterprise-eval-en-gb.iso" `
    --user eval --full-user-name 'Eval' --password-file $pw --hostname eval-windows.local `
    --locale en_GB --country GB --time-zone UTC --image-index 1 --install-additions --start-vm headless 2>&1 |
    Where-Object { $_ -notmatch 'password' }
"started $name"

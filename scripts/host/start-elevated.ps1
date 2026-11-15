# Starts a script elevated on eval-windows's desktop: opens the Run box, starts PowerShell with
# -Verb RunAs, and accepts the UAC prompt (Alt+Y). Keys go in as hardware input through
# VirtualBox, which the secure desktop accepts. Check the script's own log for the result.
param([Parameter(Mandatory)][string]$GuestScript, [string]$Name = 'eval-windows')
$vbm = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
& $vbm controlvm $Name keyboardputscancode 2a aa                # wake the screen
Start-Sleep 2
& $vbm controlvm $Name keyboardputscancode e0 5b 13 93 e0 db    # Win+R
Start-Sleep 3
& $vbm controlvm $Name keyboardputstring "powershell -Command Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File $GuestScript'"
Start-Sleep 1
& $vbm controlvm $Name keyboardputscancode 1c 9c                # Enter
Start-Sleep 12
& $vbm controlvm $Name keyboardputscancode 38 15 95 b8          # Alt+Y on the UAC prompt

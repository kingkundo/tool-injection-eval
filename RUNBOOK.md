# Runbook: Tom's home PC

How this eval runs on KUNDO-PC (Windows 11 Home, 64 GB, VirtualBox 7.2 on the Windows
hypervisor). The README covers the harness in general; this covers this machine.

## Where things are

| Path | What |
|---|---|
| `D:\eval-vms\harness` | This repo, checked out; `config.yaml` (git-ignored) and `results\` live here |
| `D:\eval-vms\venv` | Python 3.12 environment for the harness |
| `D:\eval-vms\eval-linux`, `D:\eval-vms\eval-windows` | The two VMs and their `clean` snapshots |
| `D:\eval-vms\vm-password.txt` | The VMs' `eval` password. It stays in this file: never copy it into chat, code or logs |
| `D:\eval-vms\invite-*.txt` | Invite links used once to join the VMs; never read them into chat |
| `D:\eval-vms\iso` | Install ISOs (Ubuntu 24.04.5 Server, Windows 11 Enterprise Evaluation) |
| `%USERPROFILE%\.ssh\eval_ed25519`, `config` | The key and `Host eval-*` entries the hooks use |

Both VMs are Dashcat nodes on Tom's personal account, joined **Direct mode only** (the Dashcat
connector can't reach them) and paired with this PC's bridge, `dashcat-bridge@KUNDO-PC`. Their
`clean` snapshots are taken running, signed in as `eval`, with administrator commands on and
the NAT (internet) link **off**: the harness reaches them on the host-only network only.

| VM | Address | Notes |
|---|---|---|
| eval-linux | 192.168.56.10 | Ubuntu 24.04 + GNOME on X11, 1 vCPU, 4 GB, EFI |
| eval-windows | 192.168.56.11 | Windows 11 Enterprise Evaluation (expires ~13 Feb 2027), 2 vCPUs, 8 GB |

## Running

From `D:\eval-vms\harness`, in PowerShell. `scripts\host\run.ps1` reads `ANTHROPIC_API_KEY`
from the user environment (so it works from processes started before the variable was set)
and passes everything else to `evalkit.run`.

```powershell
git pull
D:\eval-vms\venv\Scripts\python.exe -m pytest -q tests          # offline checks
powershell -File scripts\host\run.ps1 --plan --limit 50          # episodes and cost forecast

# Pilot: one process per node, in parallel; each stops at its own budget.
powershell -File scripts\host\run.ps1 --run pilot --limit 50 --node eval-linux --budget 17.5
powershell -File scripts\host\run.ps1 --run pilot --limit 50 --node eval-windows --budget 17.5
D:\eval-vms\venv\Scripts\python.exe -m evalkit.report --run pilot
```

Rerunning the same line resumes: finished episodes are skipped and failed ones rerun. The run
stops by itself (exit 3) on an out-of-credit or authentication error, or after repeated API
errors, without losing finished episodes.

To stop a run, stop its process; the episode in flight is lost and reruns next time, and the
next episode's reset puts the VM back.

## Checks while it runs

- Each process prints one line per episode with its scores. `harmed` without `attempted` is a
  scoring fault: stop and look (that is how the hook quoting bug was found).
- `dashcat-bridge nodes list` should show both nodes; `dashcat-bridge run eval-linux uptime`
  answers in under a second when a VM is up.
- A reset takes about 15 seconds. If one fails, `scripts/reset-vm.sh <vm>` by hand shows why.
- The bridge's pass lasts 6 days (`dashcat-bridge status`); sign in again before it lapses.

## Things this machine needs

- **Memory Integrity is on**, so VirtualBox runs on the Windows hypervisor, which is slow and
  fragile: Linux needs 1 vCPU (2 hang at boot) and EFI; Windows setup stalled with 4 vCPUs.
  Turning Memory Integrity off (and the hypervisor, `bcdedit /set hypervisorlaunchtype off`,
  then a restart) makes the VMs much faster, but stops WSL and Docker until it's turned back
  on. Dashcat Agent on this PC starts at sign-in, so a restart needs Tom to sign in.
- Commands VirtualBox runs inside Windows are not elevated (UAC), so Windows setup runs from
  its desktop: `scripts\host\start-elevated.ps1` opens the Run box, starts the script elevated
  and accepts the UAC prompt with the keyboard.
- With NAT off, Windows calls the host-only network unidentified and Public;
  `windows-elevated.ps1` makes unidentified networks Private and opens ssh, ping and Dashcat
  Agent (port 7420) to the host-only subnet on every profile.
- When Dashcat Agent first listens on Windows, a firewall prompt appears that nobody answers;
  left alone it adds Block rules. `pair.ps1` removes them. Clear any pop-ups on screen before
  taking a snapshot (`dashcat-bridge screenshot`; the VirtualBox screenshot can be stale).

## Rebuilding a VM

From `D:\eval-vms\harness\scripts\host`, in order: `build-linux.ps1` (or `build-windows.ps1`);
wait until `wait-vm.ps1 <vm>` reports an address (`ocr.ps1 <vm>` shows the screen while it
installs); `provision.ps1 <vm>`; for Linux, a reboot and `static-ip-linux.ps1`;
`install-agent.ps1 <vm>`; `pair.ps1 <vm>`. Then turn the NAT link off
(`VBoxManage controlvm <vm> setlinkstate1 off`), check commands, a screenshot and the dialog
through the bridge, and take the snapshot: `VBoxManage snapshot <vm> take clean`.

## Cleanup at the end

1. Copy out what to keep, then run, elevated:
   `powershell -ExecutionPolicy Bypass -File D:\eval-vms\harness\scripts\cleanup-host.ps1 -Root D:\eval-vms -Keep D:\eval-results -Uninstall`.
   It copies `results\`, deletes the VMs, ISOs, checkout, Python environment, the eval ssh key
   and config entries and the `ANTHROPIC_API_KEY` variable, and uninstalls VirtualBox and Python.
2. In Dashcat Dashboard, remove the eval-linux and eval-windows nodes; on this PC,
   `dashcat-bridge nodes remove eval-linux`, `... eval-windows`, and `dashcat-bridge logout`.
3. **Turn Memory Integrity back on** (Tom's condition when it was turned off on 16 Nov): as
   admin, `reg add HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity /v Enabled /t REG_DWORD /d 1 /f`
   and `bcdedit /set hypervisorlaunchtype auto` (both were on before the run), then restart and
   check Windows Security › Device security › Core isolation shows it on.
4. Revoke the API key in the Claude Console if it was made for this.
5. Let the PC sleep again: `powercfg /change standby-timeout-ac 15` (sleep on AC power was
   turned off for the full run on 15 Nov; it was 15 minutes before).

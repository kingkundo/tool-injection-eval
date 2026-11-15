#!/usr/bin/env bash
# Puts a VirtualBox VM back to its snapshot and waits until it answers over ssh.
#
#   scripts/reset-vm.sh <vm name> [snapshot, default clean] [ssh host, default the vm name]
#
# Take the snapshot while the VM is running, signed in and with Dashcat Agent up: restoring a
# running snapshot resumes in seconds instead of booting. VirtualBox's guest additions set the
# guest's clock on resume; without them the node may refuse a bridge pass from "the future".
# The readiness check runs `exit 0`, which both sh and Windows cmd understand.
# Set VBOXMANAGE when VBoxManage isn't on PATH (Windows: the VirtualBox install folder).
set -euo pipefail

vm="$1"
snapshot="${2:-clean}"
host="${3:-$vm}"
vbox="${VBOXMANAGE:-VBoxManage}"

state() { "$vbox" showvminfo "$vm" --machinereadable | sed -n 's/^VMState="\(.*\)"/\1/p'; }

if [[ "$(state)" != poweroff && "$(state)" != saved && "$(state)" != aborted ]]; then
  "$vbox" controlvm "$vm" poweroff >/dev/null 2>&1 || true
fi
for _ in $(seq 1 30); do
  case "$(state)" in poweroff|saved|aborted) break ;; esac
  sleep 1
done
"$vbox" snapshot "$vm" restore "$snapshot"
"$vbox" startvm "$vm" --type headless >/dev/null

for _ in $(seq 1 90); do
  if ssh -o BatchMode=yes -o ConnectTimeout=2 "$host" exit 0 >/dev/null 2>&1; then
    exit 0
  fi
  sleep 2
done
echo "$vm did not answer over ssh within 3 minutes of restoring $snapshot" >&2
exit 1

#!/usr/bin/env bash
# DESTRUCTIVE SCRATCH ARRAY ONLY. Run inside a disposable Ubuntu VM, never production.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Requires root';exit 1; }
for cmd in mdadm losetup mkfs.ext4 mount sha256sum;do command -v "$cmd" >/dev/null || exit 1;done
[[ ${I_ACCEPT_SCRATCH_RAID:-} == YES ]] || { echo 'Set I_ACCEPT_SCRATCH_RAID=YES';exit 1; }
WORK=$(mktemp -d /var/tmp/examshield-mdadm.XXXXXXXX)
MD=/dev/md/examshield-lab
A='' B='' C='' LOAD_PID=''
cleanup(){
  set +e
  [[ -n "$LOAD_PID" ]] && kill "$LOAD_PID" 2>/dev/null
  mountpoint -q "$WORK/mnt" && umount "$WORK/mnt"
  [[ -b "$MD" ]] && mdadm --stop "$MD"
  for dev in "$A" "$B" "$C"; do [[ -n "$dev" ]] && losetup -d "$dev"; done
  echo "Preserved evidence: $WORK/logs"
}
trap cleanup EXIT
mkdir -p "$WORK/mnt" "$WORK/logs"
for disk in a b c;do truncate -s 128M "$WORK/$disk.img";done
A=$(losetup --find --show "$WORK/a.img")
B=$(losetup --find --show "$WORK/b.img")
C=$(losetup --find --show "$WORK/c.img")
mdadm --create "$MD" --level=1 --raid-devices=2 --metadata=1.2 --force "$A" "$B" |& tee "$WORK/logs/create.log"
udevadm settle || true
mkfs.ext4 -F "$MD" >"$WORK/logs/mkfs.log" 2>&1
mount "$MD" "$WORK/mnt"
( while :; do
  dd if=/dev/urandom of="$WORK/mnt/exam.tmp" bs=4K count=16 status=none
  mv "$WORK/mnt/exam.tmp" "$WORK/mnt/exam.bin"
  sha256sum "$WORK/mnt/exam.bin" >>"$WORK/logs/live_checksums.log" || true
  sleep .2
done ) & LOAD_PID=$!
sleep 3
mdadm --detail "$MD" | tee "$WORK/logs/before_failure.log"
date --iso-8601=seconds | tee "$WORK/logs/failure_time.log"
mdadm "$MD" --fail "$B" |& tee "$WORK/logs/failure.log"
mdadm "$MD" --remove "$B" |& tee "$WORK/logs/remove.log"
mdadm --detail "$MD" | tee "$WORK/logs/degraded.log"
dmesg --ctime | tail -100 > "$WORK/logs/kernel_after_failure.log" || true
mdadm "$MD" --add "$C" |& tee "$WORK/logs/replacement.log"
START=$(date +%s.%N)
while grep -Eq 'resync|recovery' /proc/mdstat;do cat /proc/mdstat >>"$WORK/logs/recovery_progress.log";sleep .3;done
END=$(date +%s.%N)
awk -v a="$START" -v b="$END" 'BEGIN{printf "Observed rebuild polling duration: %.3f seconds\n",b-a}' | tee "$WORK/logs/rebuild_duration.log"
mdadm --detail "$MD" | tee "$WORK/logs/recovered.log"
kill "$LOAD_PID" 2>/dev/null || true;wait "$LOAD_PID" 2>/dev/null || true;LOAD_PID=''
sync;sha256sum "$WORK/mnt/exam.bin" | tee "$WORK/logs/final_sha256.log"
echo 'Done. Inspect raw evidence before making RAID claims.'

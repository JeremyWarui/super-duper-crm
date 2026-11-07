#!/bin/sh
# Runs `campaign-crm backup` once a day at BACKUP_HOUR_UTC (default 0, which is 03:00 in Kenya).
set -u
hour="${BACKUP_HOUR_UTC:-0}"
while :; do
	now=$(date -u +%s)
	next=$(( now - now % 86400 + hour * 3600 ))
	[ "$next" -le "$now" ] && next=$(( next + 86400 ))
	sleep $(( next - now ))
	campaign-crm backup || echo "backup failed; see the console's Health tab"
done

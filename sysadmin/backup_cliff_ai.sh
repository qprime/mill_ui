#!/bin/bash
# File: /mnt/cliff_memories/scripts/backup_cliff_ai.sh

SOURCE="/mnt/cliff_memories/cliff_ai"
DEST="/mnt/wd_backup/cliff_ai_backup"
LOG="/mnt/wd_backup/backup_log.txt"

TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')

echo "[$TIMESTAMP] Starting backup..." >> "$LOG"
rsync -av --delete "$SOURCE/" "$DEST/" >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
    echo "[$TIMESTAMP] Backup completed successfully." >> "$LOG"
else
    echo "[$TIMESTAMP] Backup FAILED!" >> "$LOG"
fi

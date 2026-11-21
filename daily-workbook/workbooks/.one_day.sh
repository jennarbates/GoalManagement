#!/bin/zsh
# Build one workbook day with a 30-minute cap. Usage: one_day.sh YYYY-MM-DD
D=$1; cd /Users/jennabates/Documents/Development/GoalManagement/daily-workbook
LOG=workbooks/batch-$D.log
PYTHONUNBUFFERED=1 ../.venv/bin/python print_batch.py --start $D --days 1 > $LOG 2>&1 &
P=$!
for i in {1..30}; do
  sleep 60
  kill -0 $P 2>/dev/null || break
  echo "$(date +%H:%M) mem: $(memory_pressure | grep -o 'free percentage: [0-9]*%') swap: $(sysctl -n vm.swapusage | awk '{print $6}')"
done
if kill -0 $P 2>/dev/null; then
  pkill -P $P; kill $P; pkill -f "dailyWorkbookLocal.py --date $D"; echo "TIMEOUT $D"; exit 2
fi
wait $P; echo "DONE $D exit=$?"

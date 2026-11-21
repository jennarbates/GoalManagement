#!/bin/zsh
# Build Nov 21 – Dec 4 one day at a time; stop on failure, timeout or low memory.
cd /Users/jennabates/Documents/Development/GoalManagement/daily-workbook/workbooks
for D in 2026-11-{21..30} 2026-12-0{1..4}; do
  free=$(memory_pressure | grep -o 'free percentage: [0-9]*' | grep -o '[0-9]*$')
  if (( free < 20 )); then echo "STOP low memory ($free% free) before $D"; exit 3; fi
  echo "START $D ($free% free)"
  out=$(./.one_day.sh $D 2>&1); echo "$out" | tail -1
  case "$out" in *"DONE $D exit=0"*) ;; *) echo "STOP at $D"; exit 1;; esac
  pdf=daily-workbook-$D.pdf; [[ -f $pdf ]] && echo "OK $D $(( $(stat -f%z $pdf) / 1000000 ))MB"
done
echo "ALL DONE"

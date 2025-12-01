#!/usr/bin/env python3
import argparse
import json
import os
import sys
import datetime
import math

# --- Configuration ---
DATA_FILE = os.path.expanduser("~/.goal_tracker.json")
WEEKS_TO_SHOW = 52

# --- Colors & Graphics ---
class Colors:
    RESET = '\033[0m'
    # Gray for empty days
    EMPTY = '\033[38;5;236m' if sys.platform != 'win32' else '\033[90m' 
    # Green scale (ANSI 256 colors for better gradients, fallback to standard green)
    L1 = '\033[38;5;22m'  # Darkest Green
    L2 = '\033[38;5;28m'
    L3 = '\033[38;5;34m'
    L4 = '\033[38;5;46m'  # Brightest Green
    
    HEADER = '\033[95m'
    BOLD = '\033[1m'

BLOCK = "■" 

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_color(count, max_count):
    if count == 0:
        return Colors.EMPTY
    
    # Calculate quartiles relative to the user's max performance
    if max_count == 0: max_count = 1
    percentage = count / max_count

    if percentage < 0.25: return Colors.L1
    if percentage < 0.50: return Colors.L2
    if percentage < 0.75: return Colors.L3
    return Colors.L4

def print_heatmap(name, history):
    """Helper to draw a single heatmap"""
    today = datetime.date.today()
    
    # Find the Sunday of the week 52 weeks ago
    start_date = today - datetime.timedelta(weeks=WEEKS_TO_SHOW)
    idx = (start_date.weekday() + 1) % 7 
    start_date -= datetime.timedelta(days=idx)

    print(f"\n{Colors.HEADER}{Colors.BOLD}Goal: {name.title()}{Colors.RESET}")
    print(f"Tracking period: {start_date} to {today}\n")

    # 1. Find max value for scaling colors
    max_val = 0
    for count in history.values():
        if count > max_val: max_val = count

    # 2. Build the grid (7 rows x WEEKS_TO_SHOW columns)
    days_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    
    for day_idx in range(7): 
        row_str = f"{days_labels[day_idx]:<4}"
        
        current_cell_date = start_date + datetime.timedelta(days=day_idx)
        
        for week in range(WEEKS_TO_SHOW + 1):
            date_str = str(current_cell_date)
            count = history.get(date_str, 0)
            
            if current_cell_date > today:
                break
                
            color = get_color(count, max_val)
            row_str += f"{color}{BLOCK}{Colors.RESET} "
            
            current_cell_date += datetime.timedelta(weeks=1)
            
        print(row_str)

def cmd_add(args, data):
    name = args.name.lower()
    if name in data:
        print(f"Goal '{name}' already exists.")
    else:
        data[name] = {"created": str(datetime.date.today()), "history": {}}
        print(f"Goal '{name}' added! Start logging with: python tracker.py log {name}")
    save_data(data)

def cmd_log(args, data):
    name = args.name.lower()
    if name not in data:
        print(f"Goal '{name}' not found. Add it first.")
        return

    today = str(datetime.date.today())
    
    # Handle amount (can be +1, -1, or raw number)
    current = data[name]["history"].get(today, 0)
    
    try:
        # If user typed "+5" or "-2"
        if args.amount.startswith('+') or args.amount.startswith('-'):
            new_amount = current + int(args.amount)
        else:
            new_amount = int(args.amount) # Absolute set
    except ValueError:
        print("Invalid amount. Use an integer.")
        return

    data[name]["history"][today] = new_amount
    save_data(data)
    print(f"Logged for '{name}'. Total today: {new_amount}")
    
    # Explicitly show just this one after logging
    print_heatmap(name, data[name]["history"])
    print(f"\nLess {Colors.EMPTY}{BLOCK}{Colors.RESET} {Colors.L1}{BLOCK}{Colors.RESET} {Colors.L2}{BLOCK}{Colors.RESET} {Colors.L3}{BLOCK}{Colors.RESET} {Colors.L4}{BLOCK}{Colors.RESET} More")

def cmd_show(args, data):
    if not data:
        print("No goals tracked yet.")
        return

    # If a specific name is provided
    if args.name:
        name = args.name.lower()
        if name not in data:
            print(f"Goal '{name}' not found.")
            return
        print_heatmap(name, data[name]["history"])
    
    # If no name provided, show ALL
    else:
        for name in data:
            print_heatmap(name, data[name]["history"])

    # Print Legend once at the bottom
    print(f"\nLess {Colors.EMPTY}{BLOCK}{Colors.RESET} {Colors.L1}{BLOCK}{Colors.RESET} {Colors.L2}{BLOCK}{Colors.RESET} {Colors.L3}{BLOCK}{Colors.RESET} {Colors.L4}{BLOCK}{Colors.RESET} More")

def cmd_list(args, data):
    if not data:
        print("No goals tracked yet.")
    else:
        print(f"{Colors.HEADER}Your Goals:{Colors.RESET}")
        for name in data:
            print(f" - {name}")

def cmd_seed(args, data):
    """Generates dummy data for testing the visual"""
    import random
    name = "demo"
    data[name] = {"created": str(datetime.date.today()), "history": {}}
    
    today = datetime.date.today()
    for i in range(365):
        d = today - datetime.timedelta(days=i)
        if random.random() > 0.3: # 70% chance of activity
            data[name]["history"][str(d)] = random.randint(1, 10)
    
    save_data(data)
    print("Demo data generated. Run: python tracker.py show demo")

def main():
    parser = argparse.ArgumentParser(description="CLI Goal Tracker with Heatmap")
    subparsers = parser.add_subparsers(dest="command")

    # Add
    p_add = subparsers.add_parser("add", help="Track a new goal")
    p_add.add_argument("name", help="Name of the goal (e.g., reading)")

    # Log
    p_log = subparsers.add_parser("log", help="Log progress")
    p_log.add_argument("name", help="Name of the goal")
    p_log.add_argument("amount", help="Amount to log (e.g., 5, +1)", default="+1", nargs="?")

    # Show
    p_show = subparsers.add_parser("show", help="Show heatmap")
    p_show.add_argument("name", help="Name of the goal", nargs="?")

    # List
    subparsers.add_parser("list", help="List all goals")
    
    # Seed (Hidden/Utility)
    subparsers.add_parser("seed", help="Generate demo data")

    args = parser.parse_args()
    data = load_data()
    
    if hasattr(args, 'command') and args.command:
        if args.command == "add":
            cmd_add(args, data)
        elif args.command == "log":
            cmd_log(args, data)
        elif args.command == "show":
            cmd_show(args, data)
        elif args.command == "list":
            cmd_list(args, data)
        elif args.command == "seed":
            cmd_seed(args, data)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

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
VALID_STATS = ["STR", "AGI", "INT", "VIT", "PER"]

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
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    GOLD = '\033[38;5;220m'
    
    # Solo Leveling "System" Blue
    SYSTEM = '\033[38;5;39m' 
    RED = '\033[31m'
    
    # Stat Colors
    STR = '\033[38;5;196m' # Red
    AGI = '\033[38;5;46m'  # Green
    INT = '\033[38;5;39m'  # Blue
    VIT = '\033[38;5;226m' # Yellow
    PER = '\033[38;5;201m' # Purple

BLOCK = "■" 

def load_data():
    default_user = {
        "xp": 0, 
        "level": 1, 
        "badges": [], 
        "stats": {"STR": 10, "AGI": 10, "INT": 10, "VIT": 10, "PER": 10}
    }
    
    if not os.path.exists(DATA_FILE):
        return {"_user": default_user}
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            # Migration: Ensure _user exists if loading old file
            if "_user" not in data:
                data["_user"] = default_user
            # Migration: Ensure stats exist
            if "stats" not in data["_user"]:
                data["_user"]["stats"] = default_user["stats"]
            return data
    except (json.JSONDecodeError, IOError):
        return {"_user": default_user}

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

def get_hunter_rank(level):
    """Returns Solo Leveling style ranks based on level."""
    if level < 10: return "E-Rank Hunter"
    if level < 20: return "D-Rank Hunter"
    if level < 30: return "C-Rank Hunter"
    if level < 45: return "B-Rank Hunter"
    if level < 60: return "A-Rank Hunter"
    if level < 80: return "S-Rank Hunter"
    if level < 100: return "National Level Hunter"
    return "Shadow Monarch"

def calculate_stats(history):
    """Calculates streaks, totals, and best day."""
    if not history:
        return 0, 0, 0, 0, "N/A"
        
    dates = sorted([datetime.datetime.strptime(d, "%Y-%m-%d").date() for d in history if history[d] > 0])
    total = sum(history.values())
    
    if not dates:
        return 0, 0, total, 0, "N/A"

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    # Current Streak
    current_streak = 0
    if today in dates:
        check_date = today
    elif yesterday in dates:
        check_date = yesterday
    else:
        check_date = None
        
    if check_date:
        current_streak = 1
        while True:
            check_date -= datetime.timedelta(days=1)
            if check_date in dates:
                current_streak += 1
            else:
                break
    
    # Longest Streak
    longest_streak = 0
    temp_streak = 0
    if dates:
        temp_streak = 1
        longest_streak = 1
        for i in range(1, len(dates)):
            if dates[i] == dates[i-1] + datetime.timedelta(days=1):
                temp_streak += 1
            else:
                temp_streak = 1
            longest_streak = max(longest_streak, temp_streak)
            
    # Daily Average
    first_date = dates[0]
    days_since_start = (today - first_date).days + 1
    avg = total / days_since_start if days_since_start > 0 else 0

    # Best Day Calculation
    days_counts = {0:0, 1:0, 2:0, 3:0, 4:0, 5:0, 6:0}
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    for date_str, count in history.items():
        if count > 0:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            days_counts[dt.weekday()] += count
            
    best_day_idx = max(days_counts, key=days_counts.get)
    best_day = day_names[best_day_idx] if days_counts[best_day_idx] > 0 else "N/A"
    
    return current_streak, longest_streak, total, avg, best_day

def calculate_weekly_performance(history):
    """Compares this week (starting Sunday) vs last week."""
    today = datetime.date.today()
    # Find start of current week (Sunday)
    idx = (today.weekday() + 1) % 7 
    start_this_week = today - datetime.timedelta(days=idx)
    start_last_week = start_this_week - datetime.timedelta(weeks=1)
    
    this_week_total = 0
    last_week_total = 0
    
    for i in range(7):
        # This week
        d1 = start_this_week + datetime.timedelta(days=i)
        this_week_total += history.get(str(d1), 0)
        
        # Last week
        d2 = start_last_week + datetime.timedelta(days=i)
        last_week_total += history.get(str(d2), 0)
        
    return this_week_total, last_week_total

# --- Gamification Logic ---
def add_xp(data, amount):
    """Adds XP and handles level ups."""
    user = data["_user"]
    user["xp"] += amount
    
    # Level formula: XP needed = Level * 100
    current_level = user["level"]
    xp_needed = current_level * 100
    
    leveled_up = False
    while user["xp"] >= xp_needed:
        user["xp"] -= xp_needed
        user["level"] += 1
        current_level = user["level"]
        xp_needed = current_level * 100
        leveled_up = True
        
    return leveled_up

def unlock_badge(data, badge_name):
    """Unlocks a badge if not already owned."""
    if badge_name not in data["_user"]["badges"]:
        data["_user"]["badges"].append(badge_name)
        print(f"\n{Colors.SYSTEM}┌──────────────────────────────────────────┐")
        print(f"│ {Colors.GOLD}BADGE ACQUIRED:{Colors.SYSTEM}                         │")
        print(f"│ {Colors.BOLD}{badge_name.center(40)}{Colors.RESET}{Colors.SYSTEM} │")
        print(f"└──────────────────────────────────────────┘{Colors.RESET}")
        return True
    return False

def check_achievements(data, goal_name):
    """Checks for milestones after an action."""
    history = data[goal_name]["history"]
    cur_streak, max_streak, total, avg, _ = calculate_stats(history)
    
    # 1. First Step
    if total > 0:
        unlock_badge(data, "The Player (Awakened)")
        
    # 2. Total Count Milestones
    if total >= 100: unlock_badge(data, "Igris (100 Total)")
    if total >= 500: unlock_badge(data, "Tank (500 Total)")
    if total >= 1000: unlock_badge(data, "Beru (1K Total)")
    if total >= 5000: unlock_badge(data, "Bellion (5K Total)")
    
    # 3. Streak Milestones
    if cur_streak >= 3: unlock_badge(data, "Heating Up (3 Day Streak)")
    if cur_streak >= 7: unlock_badge(data, "False Ranker (7 Day Streak)")
    if cur_streak >= 30: unlock_badge(data, "Monarch (30 Day Streak)")
    
    # 4. Multi-Goal (Jack of all trades)
    active_goals = [k for k in data if not k.startswith('_') and not data[k].get("archived", False)]
    if len(active_goals) >= 3:
        unlock_badge(data, "Necromancer (3 Active Goals)")

def check_daily_quest(data):
    """Checks if the user has completed the 'Daily Quest' (4 unique goals logged today)."""
    today = str(datetime.date.today())
    goals_logged_today = 0
    
    for name, info in data.items():
        if name.startswith('_'): continue
        if info.get("archived", False): continue
        
        # If logged today and value > 0
        if info["history"].get(today, 0) > 0:
            goals_logged_today += 1
            
    # 4 unique habits is the "Daily Quest" (Pushup, Situp, Squat, Run)
    if goals_logged_today == 4:
        # Check if we already awarded daily bonus? 
        # (We store daily bonus state in _user history to prevent double dipping)
        user = data["_user"]
        if "daily_quests" not in user: user["daily_quests"] = {}
        
        if user["daily_quests"].get(today) != True:
            user["daily_quests"][today] = True
            print(f"\n{Colors.SYSTEM}┌──────────────────────────────────────────┐")
            print(f"│ {Colors.BOLD}[DAILY QUEST] COMPLETED{Colors.SYSTEM}                  │")
            print(f"│ Rewards:                                 │")
            print(f"│ {Colors.GOLD}Status Recovery (Full Heal){Colors.SYSTEM}              │")
            print(f"│ {Colors.GOLD}+50 Experience Points{Colors.SYSTEM}                    │")
            print(f"└──────────────────────────────────────────┘{Colors.RESET}")
            return 50 # Return bonus XP
            
    return 0

def print_heatmap(name, goal_data):
    """Helper to draw a single heatmap with stats"""
    history = goal_data["history"]
    unit = goal_data.get("unit", "")
    unit_str = f" ({unit})" if unit else ""
    stat = goal_data.get("stat", "")
    stat_str = f" [{stat}]" if stat else ""

    # --- Stats Calculation ---
    cur_streak, max_streak, total, avg, best_day = calculate_stats(history)
    this_week, last_week = calculate_weekly_performance(history)
    
    # Stats formatting
    trend = ""
    if this_week > last_week:
        trend = f"{Colors.L4}▲{Colors.RESET}"
    elif this_week < last_week:
        trend = f"{Colors.YELLOW}▼{Colors.RESET}"
    
    print(f"\n{Colors.HEADER}{Colors.BOLD}Goal: {name.title()}{unit_str}{Colors.SYSTEM}{stat_str}{Colors.RESET}")
    
    # Print Stats Bar
    print(f"  {Colors.CYAN}Streak:{Colors.RESET} {cur_streak} days (Best: {max_streak})  "
          f"|  {Colors.CYAN}Total:{Colors.RESET} {total}  "
          f"|  {Colors.CYAN}Best Day:{Colors.RESET} {best_day}  "
          f"|  {Colors.CYAN}Week:{Colors.RESET} {this_week} vs {last_week} prev {trend}")
    
    # --- Graph Setup ---
    today = datetime.date.today()
    start_date = today - datetime.timedelta(weeks=WEEKS_TO_SHOW)
    idx = (start_date.weekday() + 1) % 7 
    start_date -= datetime.timedelta(days=idx)
    
    print(f"  {Colors.EMPTY}Tracking period: {start_date} to {today}{Colors.RESET}\n")

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
    if name.startswith('_'): 
        print("Cannot use names starting with underscore.")
        return

    unit = args.unit if args.unit else ""
    stat = args.stat.upper() if args.stat else ""
    
    if stat and stat not in VALID_STATS:
        print(f"Invalid stat. Choose from: {', '.join(VALID_STATS)}")
        return
    
    if name in data:
        # Check if it was archived, if so, restore it
        if data[name].get("archived", False):
            print(f"Goal '{name}' was archived. Restoring it to active list.")
            data[name]["archived"] = False
            if unit: data[name]["unit"] = unit 
            if stat: data[name]["stat"] = stat
            save_data(data)
        else:
            print(f"Goal '{name}' already exists.")
    else:
        data[name] = {
            "created": str(datetime.date.today()), 
            "history": {}, 
            "archived": False,
            "unit": unit,
            "stat": stat
        }
        unit_msg = f" (Unit: {unit})" if unit else ""
        stat_msg = f" (Stat: {stat})" if stat else ""
        print(f"Goal '{name}' added{unit_msg}{stat_msg}! Start logging with: python tracker.py log {name}")
    save_data(data)

def cmd_log(args, data):
    name = args.name.lower()
    if name not in data or name.startswith('_'):
        print(f"Goal '{name}' not found. Add it first.")
        return

    # Optional: Warn if logging to archived goal
    if data[name].get("archived", False):
        print(f"{Colors.HEADER}Note: '{name}' is currently archived.{Colors.RESET}")

    # Determine Date
    if args.date:
        try:
            # Validate format
            datetime.datetime.strptime(args.date, "%Y-%m-%d")
            log_date = args.date
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD.")
            return
    else:
        log_date = str(datetime.date.today())

    unit = data[name].get("unit", "")
    unit_str = f" {unit}" if unit else ""

    # Handle amount (can be +1, -1, or raw number)
    current = data[name]["history"].get(log_date, 0)
    
    try:
        # If user typed "+5" or "-2"
        if args.amount.startswith('+') or args.amount.startswith('-'):
            amount_delta = int(args.amount)
            new_amount = current + amount_delta
        else:
            new_amount = int(args.amount) # Absolute set
            amount_delta = new_amount - current # Calculate actual change
    except ValueError:
        print("Invalid amount. Use an integer.")
        return

    data[name]["history"][log_date] = new_amount
    
    # --- Gamification: Add XP & Stats ---
    if amount_delta > 0:
        xp_gain = 10
        # Streak Bonus
        cur_streak, _, _, _, _ = calculate_stats(data[name]["history"])
        if cur_streak > 1:
            streak_bonus = min(cur_streak * 2, 20) 
            xp_gain += streak_bonus
            print(f"{Colors.GOLD}+{xp_gain} XP (Includes Streak Bonus!){Colors.RESET}")
        else:
            print(f"{Colors.GOLD}+{xp_gain} XP{Colors.RESET}")
            
        # Daily Quest Bonus Check
        if log_date == str(datetime.date.today()):
            quest_bonus = check_daily_quest(data)
            xp_gain += quest_bonus
        
        # Stat Increase
        stat_name = data[name].get("stat")
        if stat_name:
            data["_user"]["stats"][stat_name] += 1
            # Color code the stat
            stat_color = getattr(Colors, stat_name, Colors.RESET)
            print(f"{stat_color}[{stat_name} INCREASED!]{Colors.RESET}")

        leveled_up = add_xp(data, xp_gain)
        if leveled_up:
            new_lvl = data["_user"]["level"]
            print(f"\n{Colors.SYSTEM}┌──────────────────────────────────────────┐")
            print(f"│ {Colors.BOLD}ALERT: LEVEL UP!{Colors.SYSTEM}                         │")
            print(f"│ You have reached {Colors.BOLD}Level {new_lvl}{Colors.RESET}{Colors.SYSTEM}                  │")
            print(f"└──────────────────────────────────────────┘{Colors.RESET}\n")
        
        check_achievements(data, name)

    save_data(data)
    print(f"Logged for '{name}' on {log_date}. Total: {new_amount}{unit_str}")
    
    # Explicitly show just this one after logging
    print_heatmap(name, data[name])
    print(f"\nLess {Colors.EMPTY}{BLOCK}{Colors.RESET} {Colors.L1}{BLOCK}{Colors.RESET} {Colors.L2}{BLOCK}{Colors.RESET} {Colors.L3}{BLOCK}{Colors.RESET} {Colors.L4}{BLOCK}{Colors.RESET} More")

def cmd_show(args, data):
    if len(data) <= 1: # Just _user
        print("No goals tracked yet.")
        return

    # If a specific name is provided, show it even if archived
    if args.name:
        name = args.name.lower()
        if name not in data or name.startswith('_'):
            print(f"Goal '{name}' not found.")
            return
        
        if data[name].get("archived", False):
            print(f"({Colors.HEADER}ARCHIVED{Colors.RESET}) ", end="")
            
        print_heatmap(name, data[name])
    
    # If no name provided, show ALL ACTIVE
    else:
        active_goals = [name for name in data if not name.startswith('_') and not data[name].get("archived", False)]
        if not active_goals:
            print("No active goals to show. Use 'python tracker.py list' or 'python tracker.py archives'.")
            return
            
        for name in active_goals:
            print_heatmap(name, data[name])

    # Print Legend once at the bottom
    print(f"\nLess {Colors.EMPTY}{BLOCK}{Colors.RESET} {Colors.L1}{BLOCK}{Colors.RESET} {Colors.L2}{BLOCK}{Colors.RESET} {Colors.L3}{BLOCK}{Colors.RESET} {Colors.L4}{BLOCK}{Colors.RESET} More")

def cmd_list(args, data):
    active_goals = [name for name in data if not name.startswith('_') and not data[name].get("archived", False)]
    
    if not active_goals:
        print("No active goals.")
    else:
        print(f"{Colors.HEADER}Active Goals:{Colors.RESET}")
        for name in active_goals:
            unit = data[name].get("unit", "")
            unit_str = f" [{unit}]" if unit else ""
            stat = data[name].get("stat", "")
            stat_str = f" ({stat})" if stat else ""
            print(f" - {name}{unit_str}{stat_str}")

def cmd_list_archives(args, data):
    archived_goals = [name for name in data if not name.startswith('_') and data[name].get("archived", False)]
    
    if not archived_goals:
        print("No archived goals.")
    else:
        print(f"{Colors.HEADER}Archived Goals:{Colors.RESET}")
        for name in archived_goals:
            unit = data[name].get("unit", "")
            unit_str = f" [{unit}]" if unit else ""
            print(f" - {name}{unit_str}")

def cmd_profile(args, data):
    user = data["_user"]
    level = user["level"]
    xp = user["xp"]
    badges = user["badges"]
    stats = user["stats"]
    xp_next = level * 100
    rank = get_hunter_rank(level)
    
    # Progress Bar
    bar_len = 20
    filled = int(bar_len * (xp / xp_next))
    bar = f"{Colors.SYSTEM}{'█' * filled}{Colors.EMPTY}{'█' * (bar_len - filled)}{Colors.RESET}"
    
    print(f"\n{Colors.SYSTEM}┌──────────────────────────────────────────┐")
    print(f"│ {Colors.BOLD}STATUS WINDOW{Colors.RESET}{Colors.SYSTEM}                            │")
    print(f"├──────────────────────────────────────────┤")
    print(f"│ Name: {Colors.BOLD}Player{Colors.RESET}{Colors.SYSTEM}                             │")
    print(f"│ Level: {Colors.BOLD}{level}{Colors.RESET}{Colors.SYSTEM}                                │")
    print(f"│ Class: {Colors.BOLD}{rank:<30}{Colors.RESET}{Colors.SYSTEM}│")
    print(f"│ XP: {xp}/{xp_next}  {bar}{Colors.SYSTEM}   │")
    print(f"├──────────────────────────────────────────┤")
    print(f"│ {Colors.STR}STR: {stats['STR']:<5}{Colors.SYSTEM}                           │")
    print(f"│ {Colors.AGI}AGI: {stats['AGI']:<5}{Colors.SYSTEM}                           │")
    print(f"│ {Colors.INT}INT: {stats['INT']:<5}{Colors.SYSTEM}                           │")
    print(f"│ {Colors.VIT}VIT: {stats['VIT']:<5}{Colors.SYSTEM}                           │")
    print(f"│ {Colors.PER}PER: {stats['PER']:<5}{Colors.SYSTEM}                           │")
    print(f"└──────────────────────────────────────────┘{Colors.RESET}")
    
    print(f"\n{Colors.CYAN}Shadows Extracted (Badges) [{len(badges)}]:{Colors.RESET}")
    if not badges:
        print(f"{Colors.EMPTY}(No shadows yet. Continue the quest.){Colors.RESET}")
    else:
        for badge in badges:
            print(f" {Colors.SYSTEM}★{Colors.RESET} {badge}")
    print("")

def cmd_delete(args, data):
    name = args.name.lower()
    if name not in data or name.startswith('_'):
        print(f"Goal '{name}' not found.")
        return
    
    confirm = input(f"Are you sure you want to delete '{name}' and all its history? (y/N): ")
    if confirm.lower() == 'y':
        del data[name]
        save_data(data)
        print(f"Goal '{name}' deleted.")
    else:
        print("Operation cancelled.")

def cmd_archive(args, data):
    name = args.name.lower()
    if name not in data or name.startswith('_'):
        print(f"Goal '{name}' not found.")
        return
    
    data[name]["archived"] = True
    save_data(data)
    print(f"Goal '{name}' has been archived. It is hidden from default lists.")

def cmd_restore(args, data):
    name = args.name.lower()
    if name not in data or name.startswith('_'):
        print(f"Goal '{name}' not found.")
        return
    
    data[name]["archived"] = False
    save_data(data)
    print(f"Goal '{name}' restored to active list.")

def cmd_seed(args, data):
    """Generates dummy data for testing the visual"""
    import random
    name = "demo"
    data[name] = {"created": str(datetime.date.today()), "history": {}, "archived": False, "unit": "points", "stat": "INT"}
    
    today = datetime.date.today()
    for i in range(365):
        d = today - datetime.timedelta(days=i)
        if random.random() > 0.3: # 70% chance of activity
            data[name]["history"][str(d)] = random.randint(1, 10)
    
    save_data(data)
    print("Demo data generated. Run: python tracker.py show demo")

def main():
    epilog_text = f"""
{Colors.HEADER}{Colors.BOLD}=== GAMIFICATION & SYSTEMS ==={Colors.RESET}

{Colors.BOLD}1. RPG STATS SYSTEM (Solo Leveling){Colors.RESET}
   Assign attributes to your real-life goals to build your character.
   Use {Colors.CYAN}-s{Colors.RESET} or {Colors.CYAN}--stat{Colors.RESET} when adding a goal.
   
   {Colors.BOLD}Valid Stats:{Colors.RESET}
   - {Colors.STR}STR{Colors.RESET} (Strength): Physical power (Pushups, Weights)
   - {Colors.AGI}AGI{Colors.RESET} (Agility): Speed and dexterity (Running, Yoga)
   - {Colors.INT}INT{Colors.RESET} (Intelligence): Knowledge (Reading, Coding)
   - {Colors.VIT}VIT{Colors.RESET} (Vitality): Health and stamina (Water, Sleep)
   - {Colors.PER}PER{Colors.RESET} (Perception): Focus and awareness (Meditation)

   {Colors.BOLD}Example:{Colors.RESET} 
   python tracker.py add running -s AGI

{Colors.BOLD}2. UNITS{Colors.RESET}
   Track specific metrics instead of just "count".
   Use {Colors.CYAN}-u{Colors.RESET} or {Colors.CYAN}--unit{Colors.RESET} to define the measurement.
   
   {Colors.BOLD}Example:{Colors.RESET}
   python tracker.py add reading -u pages

{Colors.BOLD}3. DAILY QUEST{Colors.RESET}
   Log progress on {Colors.BOLD}4 unique goals{Colors.RESET} in a single day to complete
   the "Preparation" Daily Quest for a massive XP bonus.
"""

    parser = argparse.ArgumentParser(
        description="CLI Goal Tracker with Heatmap",
        epilog=epilog_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command")

    # Add
    p_add = subparsers.add_parser("add", help="Track a new goal")
    p_add.add_argument("name", help="Name of the goal (e.g., reading)")
    p_add.add_argument("-u", "--unit", help="Unit of measurement (e.g., pages, mins)", default="")
    p_add.add_argument("-s", "--stat", help=f"RPG Stat ({', '.join(VALID_STATS)})", default="")

    # Delete
    p_delete = subparsers.add_parser("delete", help="Delete a goal")
    p_delete.add_argument("name", help="Name of the goal")
    
    # Archive
    p_archive = subparsers.add_parser("archive", help="Archive a goal (hide without deleting)")
    p_archive.add_argument("name", help="Name of the goal")

    # Restore
    p_restore = subparsers.add_parser("restore", help="Restore an archived goal")
    p_restore.add_argument("name", help="Name of the goal")
    
    # Archives (List)
    subparsers.add_parser("archives", help="List archived goals")

    # Log
    p_log = subparsers.add_parser("log", help="Log progress")
    p_log.add_argument("name", help="Name of the goal")
    p_log.add_argument("amount", help="Amount to log (e.g., 5, +1)", default="+1", nargs="?")
    p_log.add_argument("-d", "--date", help="Date to log for (YYYY-MM-DD)", default=None)

    # Show
    p_show = subparsers.add_parser("show", help="Show heatmap")
    p_show.add_argument("name", help="Name of the goal", nargs="?")

    # List
    subparsers.add_parser("list", help="List active goals")
    
    # Profile (New!)
    subparsers.add_parser("profile", help="View your Level and Badges")
    
    # Seed (Hidden/Utility)
    subparsers.add_parser("seed", help="Generate demo data")

    args = parser.parse_args()
    data = load_data()
    
    if hasattr(args, 'command') and args.command:
        if args.command == "add":
            cmd_add(args, data)
        elif args.command == "delete":
            cmd_delete(args, data)
        elif args.command == "archive":
            cmd_archive(args, data)
        elif args.command == "restore":
            cmd_restore(args, data)
        elif args.command == "archives":
            cmd_list_archives(args, data)
        elif args.command == "log":
            cmd_log(args, data)
        elif args.command == "show":
            cmd_show(args, data)
        elif args.command == "list":
            cmd_list(args, data)
        elif args.command == "profile":
            cmd_profile(args, data)
        elif args.command == "seed":
            cmd_seed(args, data)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

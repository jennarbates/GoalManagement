⚔️ CLI Goal Tracker & Leveling System
"The System will help the Player grow."
A zero-dependency Python tool that gamifies your real-life habits. Track your goals, view GitHub-style contribution heatmaps, earn XP, unlock achievements, and level up your Hunter Rank.
Inspired by Solo Leveling, this tool turns your terminal into a Status Window for your life.
🌟 Features
📊 Visual Heatmaps: See your consistency at a glance with beautiful, color-coded grids.
🎮 RPG Leveling: Earn XP for every log. Level up from E-Rank to National Level Hunter.
💪 Attribute System: Assign stats (STR, INT, AGI) to your habits and watch your parameters grow.
🏆 Badges & Achievements: Unlock "Shadows" (Badges) for streaks and milestones.
📜 Daily Quest: Complete 4 unique habits in a single day to trigger the "Preparation" quest bonus.
📅 Time Travel: Forgot to log yesterday? Backfill data easily.
⚡ Zero Dependencies: Runs on standard Python 3. No pip install required.
🚀 Quick Start
1. Download
Save the script as tracker.py.
2. Setup (Optional)
Make it executable and add an alias for quick access.
chmod +x tracker.py
# Add to your .bashrc or .zshrc:
alias track="python3 ~/path/to/tracker.py"


3. Start Your Journey
# Add your first goal (Assign Intelligence stat)
track add reading -u pages -s INT

# Log your progress
track log reading 20


🕹️ Command Guide
add - Create a New Goal
Start tracking a habit. You can assign a Unit and an Attribute.
# Syntax
track add <name> -u <unit> -s <stat>

# Examples
track add pushups -u reps -s STR
track add coding -u hours -s INT
track add running -u km -s AGI


log - Record Progress
Log your activity. You earn 10 XP per log, plus Streak Bonuses.
# Log for today
track log pushups 50

# Log for a past date (Backfill)
track log coding 2 -d 2023-10-27

# Decrease count (fix mistakes)
track log running -5


show - View Heatmap
See your activity grid, streaks, and weekly trends.
# Show specific goal
track show reading

# Show dashboard for ALL active goals
track show


profile - The Status Window
View your Hunter Rank, Level, XP Bar, Stats, and collected Badges.
track profile


🛡️ The System
Hunter Ranks
Your rank is determined by your total Level.
Level 1-9: E-Rank
Level 10-19: D-Rank
Level 20-29: C-Rank
...and beyond. Can you reach Shadow Monarch?
Daily Quest: "Preparation"
Objective: Log progress on 4 different goals in a single day.
Reward: Status Recovery (Flavor) + 50 XP Bonus.
Attribute System
Build your character by assigning stats to goals:
🔴 STR (Strength): Physical power (Weights, Calisthenics)
🟢 AGI (Agility): Speed & Dexterity (Running, Sports)
🔵 INT (Intelligence): Knowledge (Reading, Studying, Coding)
🟡 VIT (Vitality): Health (Sleep, Water, Diet)
🟣 PER (Perception): Focus (Meditation, Planning)
📂 Data Management
All data is stored locally in a simplified JSON file:
~/.goal_tracker.json
You can manually back up this file if you want to save your progress on another machine.
Archiving:
Stop seeing a goal without deleting its history.
track archive old_goal
# Restore it later
track restore old_goal


🤝 Contributing
Feel free to fork this script and add your own "System" features!
Dungeon Keys?
Shop System?
Class Changes?
The possibilities are endless. Arise.


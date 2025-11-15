import pandas as pd
import json
from datetime import datetime

# Load data
with open("activity_log.json") as f:
    data = json.load(f)

# Convert to DataFrame
df = pd.DataFrame(data)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)
df['date'] = df['timestamp'].dt.date
df['month'] = df['timestamp'].dt.to_period('M')
df['hour'] = df['timestamp'].dt.hour
df['weekday'] = df['timestamp'].dt.day_name()

# === Overall Activity ===
total_hours = len(df)
active_hours = df['active'].sum()
active_percent = (active_hours / total_hours) * 100

print("=== Clash of Clans Activity Report ===\n")
print(f"Total hours logged: {total_hours}")
print(f"Active hours: {active_hours}")
print(f"Overall activity rate: {active_percent:.1f}%\n")

# === Most Active Day ===
day_activity = df.groupby('date')['active'].sum()
most_active_day = day_activity.idxmax()
most_active_day_fmt = most_active_day.strftime('%d.%m.%Y')
print(f"Most active day: {most_active_day_fmt} with {day_activity.max()} active hours")

# === Most Active Month ===
month_activity = df.groupby('month')['active'].mean() * 100
most_active_month = month_activity.idxmax()
print(f"Most active month: {most_active_month.strftime('%m.%Y')} with {month_activity.max():.1f}% activity\n")

# === Weekday Breakdown ===
weekday_activity = df.groupby('weekday')['active'].mean() * 100
print("Activity by weekday (% of hours active):")
for day, pct in weekday_activity.sort_values(ascending=False).items():
    print(f"  {day:<10} {pct:5.1f}%")
print()

# === Most Active Hour ===
hour_activity = df.groupby('hour')['active'].mean() * 100
most_active_hour = hour_activity.idxmax()
print(f"Most active hour of the day: {most_active_hour:02d}:00 with {hour_activity.max():.1f}% activity\n")

# === Streak Calculations ===
def find_streaks(df, active_state=True):
    """Find streaks of consecutive active or inactive states."""
    streaks = []
    start_idx = None
    current_len = 0

    for i, row in df.iterrows():
        if row['active'] == active_state:
            if current_len == 0:
                start_idx = i
            current_len += 1
        else:
            if current_len > 0:
                end_idx = i - 1
                streaks.append((start_idx, end_idx, current_len))
                current_len = 0
    if current_len > 0:
        streaks.append((start_idx, len(df) - 1, current_len))
    return streaks

active_streaks = find_streaks(df, True)
inactive_streaks = find_streaks(df, False)

# Longest active streak
if active_streaks:
    longest_active = max(active_streaks, key=lambda x: x[2])
    start_a = df.loc[longest_active[0], 'timestamp']
    end_a = df.loc[longest_active[1], 'timestamp']
    print(f"Longest active streak: {longest_active[2]} hours "
          f"({start_a.strftime('%d.%m.%Y %H:%M')} – {end_a.strftime('%d.%m.%Y %H:%M')})")
else:
    print("No active streaks found.")

# Longest non-active streak
if inactive_streaks:
    longest_inactive = max(inactive_streaks, key=lambda x: x[2])
    start_i = df.loc[longest_inactive[0], 'timestamp']
    end_i = df.loc[longest_inactive[1], 'timestamp']
    print(f"Longest non-active streak: {longest_inactive[2]} hours "
          f"({start_i.strftime('%d.%m.%Y %H:%M')} – {end_i.strftime('%d.%m.%Y %H:%M')})")
else:
    print("No non-active streaks found.")
print()

# === Average Daily Active Hours ===
daily_activity = df.groupby('date')['active'].sum()
avg_daily_active_hours = daily_activity[daily_activity > 0].mean()
print(f"Average daily active hours (on active days): {avg_daily_active_hours:.2f} hours")

# === Number of Days with Any Activity ===
total_days = df['date'].nunique()
active_days = (daily_activity > 0).sum()
active_day_ratio = (active_days / total_days) * 100
print(f"Days with any activity: {active_days} out of {total_days} days ({active_day_ratio:.1f}%)")

# === Average Active Hours Range per Day ===
# Find average "start" and "end" of activity for each day
day_ranges = []
for day, group in df.groupby('date'):
    active_hours = group[group['active']]['hour']
    if not active_hours.empty:
        start = active_hours.min()
        end = active_hours.max()
        day_ranges.append((start, end))

if day_ranges:
    avg_start = int(sum(s for s, _ in day_ranges) / len(day_ranges))
    avg_end = int(sum(e for _, e in day_ranges) / len(day_ranges))
    print(f"Average active hours range per day: {avg_start:02d}:00–{avg_end:02d}:00")
else:
    print("No activity ranges found.")

print("\n=== End of Report ===")

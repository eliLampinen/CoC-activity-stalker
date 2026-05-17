import requests
import json
from datetime import datetime
import os

# Import configuration variables
from configFile import API_TOKEN, USER_TAG

# Set base directory and file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAST_POLL_FILE = os.path.join(BASE_DIR, "last_poll.json")
ACTIVITY_LOG_FILE = os.path.join(BASE_DIR, "activity_log.json")

# Player endpoint
PLAYER_URL = f"https://api.clashofclans.com/v1/players/%23{USER_TAG}"

# Headers for the API request
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json"
}


def fetch_player_data():
    """Fetch player data from the API."""
    response = requests.get(PLAYER_URL, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching data: {response.status_code}, {response.text}")
        return None


def save_last_poll(data):
    """Save last poll data to a file."""
    with open(LAST_POLL_FILE, "w") as f:
        json.dump(data, f)


def load_last_poll():
    """Load last poll data from a file."""
    try:
        with open(LAST_POLL_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def log_activity(timestamp, active):
    """Log activity to a file."""
    log_entry = {"timestamp": timestamp, "active": active}
    try:
        with open(ACTIVITY_LOG_FILE, "r") as f:
            logs = json.load(f)
    except FileNotFoundError:
        logs = []

    logs.append(log_entry)

    with open(ACTIVITY_LOG_FILE, "w") as f:
        json.dump(logs, f, indent=4)


def detect_activity(last_poll, current_data):
    """Detect if the player has been active."""
    # Extract relevant data
    keys_to_track = [
        "attackWins",
        "donations",
        "clanCapitalContributions",
        "builderBaseTrophies",
        "warStars"
    ]

    # Check if any of the tracked keys have changed
    for key in keys_to_track:
        if current_data.get(key, 0) > last_poll.get(key, 0):
            return True

    # Check achievements for any progress
    # List of achievements to exclude
    excluded_achievements = [
        "Bigger Coffers", "Bigger & Better", "Discover New Troops",
        "Empire Builder", "Unbreakable", "Keep Your Account Safe!",
        "Master Engineering", "Next Generation Model"
    ]

    # Filter out excluded achievements
    last_achievements = {
        ach["name"]: ach["value"] for ach in last_poll.get("achievements", [])
        if ach["name"] not in excluded_achievements
    }
    current_achievements = {
        ach["name"]: ach["value"] for ach in current_data.get("achievements", [])
        if ach["name"] not in excluded_achievements
    }

    for name, current_value in current_achievements.items():
        last_value = last_achievements.get(name, 0)
        if current_value > last_value:
            return True

    return False


def main():
    """Main script logic."""
    current_time = datetime.now().isoformat()  # Get the current timestamp

    # Fetch current player data
    current_data = fetch_player_data()
    if not current_data:
        return

    # Load last poll data
    last_poll = load_last_poll()

    if last_poll:
        # Detect activity
        active = detect_activity(last_poll, current_data)

        # Log activity
        log_activity(current_time, active)

        # Print status for logs
        if active:
            print(f"[{current_time}] Player has been online recently.")
        else:
            print(f"[{current_time}] Player has not been online recently.")
    else:
        # If no last poll data exists, initialize it
        print(f"[{current_time}] Initializing data for the first poll.")

    # Save current data as the last poll
    save_last_poll({
        "attackWins": current_data.get("attackWins", 0),
        "donations": current_data.get("donations", 0),
        "clanCapitalContributions": current_data.get("clanCapitalContributions", 0),
        "builderBaseTrophies": current_data.get("builderBaseTrophies", 0),
        "warStars": current_data.get("warStars", 0),
        "achievements": current_data.get("achievements", [])
    })


if __name__ == "__main__":
    main()

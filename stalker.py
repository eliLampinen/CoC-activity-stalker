import json
import os
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from configFile import API_TOKEN, USER_TAG


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAST_POLL_FILE = os.path.join(BASE_DIR, "last_poll.json")
ACTIVITY_LOG_FILE = os.path.join(BASE_DIR, "activity_log.json")

API_BASE_URL = "https://api.clashofclans.com/v1"


HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
}


# Fields currently shown by the public player endpoint and useful for activity inference.
# Some reset seasonally or can move down, so detection logic handles them carefully.
TOP_LEVEL_FIELDS = [
    "attackWins",
    "defenseWins",
    "donations",
    "donationsReceived",
    "clanCapitalContributions",
    "builderBaseTrophies",
    "bestBuilderBaseTrophies",
    "trophies",
    "bestTrophies",
    "warStars",
    "expLevel",
    "townHallLevel",
    "townHallWeaponLevel",
    "builderHallLevel",
]


# Do not use these as reliable activity indicators.
# They are account setup / village unlock / one-time progression style achievements
# and can create noisy historical diffs.
EXCLUDED_ACHIEVEMENTS = {
    "Bigger Coffers",
    "Bigger & Better",
    "Discover New Troops",
    "Empire Builder",
    "Unbreakable",
    "Keep Your Account Safe!",
    "Master Engineering",
    "Next Generation Model",
}


def normalize_tag(tag: str) -> str:
    """Normalize a CoC player tag to '#ABC123'."""
    tag = str(tag).strip().upper()
    if not tag.startswith("#"):
        tag = f"#{tag}"
    return tag


def player_url(tag: str) -> str:
    """
    Build player endpoint URL.

    CoC docs require the leading # to be URL-encoded, e.g. #2ABC -> %232ABC.
    """
    encoded_tag = quote(normalize_tag(tag), safe="")
    return f"{API_BASE_URL}/players/{encoded_tag}"


def now_iso() -> str:
    """Use timezone-aware local timestamp."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fetch_player_data() -> dict | None:
    """Fetch player data from the Clash of Clans API."""
    try:
        response = requests.get(player_url(USER_TAG), headers=HEADERS, timeout=30)
    except requests.RequestException as exc:
        print(f"Error fetching data: request failed: {exc}")
        return None

    if response.status_code == 200:
        return response.json()

    print(f"Error fetching data: {response.status_code}, {response.text}")
    return None


def load_json_file(path: str, default):
    """Load JSON file safely."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        print(f"Warning: '{path}' contains invalid JSON. Starting from default.")
        return default


def save_json_file(path: str, data) -> None:
    """Save JSON file atomically enough for a cron-style script."""
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, path)



def as_number(value, default=0):
    """Coerce API-ish values to number."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_name(value) -> str:
    """
    Normalize item names.

    The real API usually returns strings, but some generated docs show object-shaped names.
    This keeps comparison stable if localized/object names appear.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("en", "name", "value"):
            if key in value:
                return str(value[key])
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def item_key(item: dict) -> str:
    """Stable key for troops/heroes/spells/achievements/equipment-like items."""
    name = normalize_name(item.get("name", "unknown"))
    village = item.get("village", "")
    return f"{name}|{village}"


def normalize_item_collection(items: list[dict], fields: list[str]) -> dict:
    """Normalize list of API objects into a comparable dict."""
    normalized = {}

    for item in items or []:
        if not isinstance(item, dict):
            continue

        key = item_key(item)
        normalized[key] = {}

        for field in fields:
            if field in item:
                value = item[field]
                if isinstance(value, int | float | bool):
                    normalized[key][field] = value
                else:
                    normalized[key][field] = normalize_name(value)

    return normalized


def normalize_achievements(achievements: list[dict]) -> dict:
    """Normalize achievement values, excluding noisy setup/unlock achievements."""
    normalized = {}

    for ach in achievements or []:
        if not isinstance(ach, dict):
            continue

        name = normalize_name(ach.get("name", "unknown"))
        if name in EXCLUDED_ACHIEVEMENTS:
            continue

        village = ach.get("village", "")
        key = f"{name}|{village}"

        normalized[key] = {
            "value": as_number(ach.get("value", 0)),
            "stars": as_number(ach.get("stars", 0)),
            "target": as_number(ach.get("target", 0)),
        }

    return normalized


def build_snapshot(player: dict) -> dict:
    """
    Build a compact, stable snapshot for comparison.

    This keeps last_poll.json small and avoids comparing noisy API fields like icons.
    """
    snapshot = {
        "schema_version": 2,
        "tag": player.get("tag"),
        "name": player.get("name"),
        "captured_at": now_iso(),
        "top_level": {},
        "achievements": normalize_achievements(player.get("achievements", [])),
        "troops": normalize_item_collection(
            player.get("troops", []),
            ["level", "maxLevel", "village", "superTroopIsActive"],
        ),
        "heroes": normalize_item_collection(
            player.get("heroes", []),
            ["level", "maxLevel", "village", "superTroopIsActive"],
        ),
        "spells": normalize_item_collection(
            player.get("spells", []),
            ["level", "maxLevel", "village"],
        ),
        "equipment": normalize_item_collection(
            player.get("heroEquipment", []),
            ["level", "maxLevel", "village"],
        ),
        "labels": sorted(
            normalize_name(label.get("name", "unknown"))
            for label in player.get("labels", [])
            if isinstance(label, dict)
        ),
        "clan": {
            "tag": (player.get("clan") or {}).get("tag"),
            "name": (player.get("clan") or {}).get("name"),
            "role": player.get("role"),
        },
        "league": {
            "id": (player.get("league") or {}).get("id"),
            "name": normalize_name((player.get("league") or {}).get("name", "")),
        },
        "builderBaseLeague": {
            "id": (player.get("builderBaseLeague") or {}).get("id"),
            "name": normalize_name((player.get("builderBaseLeague") or {}).get("name", "")),
        },
    }

    for field in TOP_LEVEL_FIELDS:
        snapshot["top_level"][field] = as_number(player.get(field, 0))

    return snapshot


def load_last_poll() -> dict | None:
    """Load previous snapshot, including old v1 last_poll.json format."""
    data = load_json_file(LAST_POLL_FILE, None)
    if not data:
        return None

    # New format.
    if data.get("schema_version") == 2 and "top_level" in data:
        return data

    # Backward compatibility with your old last_poll.json.
    legacy = {
        "schema_version": 2,
        "captured_at": None,
        "top_level": {},
        "achievements": normalize_achievements(data.get("achievements", [])),
        "troops": {},
        "heroes": {},
        "spells": {},
        "equipment": {},
        "labels": [],
        "clan": {},
        "league": {},
        "builderBaseLeague": {},
    }

    for field in TOP_LEVEL_FIELDS:
        legacy["top_level"][field] = as_number(data.get(field, 0))

    return legacy


def log_activity(timestamp: str, active: bool, reasons: list[str]) -> None:
    """
    Log activity.

    Keeps old shape compatible: timestamp + active.
    Adds reasons so you can debug why a poll was marked active.
    """
    logs = load_json_file(ACTIVITY_LOG_FILE, [])
    logs.append(
        {
            "timestamp": timestamp,
            "active": bool(active)
            #"reasons": reasons,
        }
    )
    save_json_file(ACTIVITY_LOG_FILE, logs)


def compare_numeric_dict(
    old: dict,
    new: dict,
    prefix: str,
    only_increases: bool = True,
) -> list[str]:
    """Compare numeric dictionaries."""
    reasons = []

    for key, new_value in new.items():
        old_value = old.get(key)

        if old_value is None:
            continue

        old_num = as_number(old_value, None)
        new_num = as_number(new_value, None)

        if old_num is None or new_num is None:
            continue

        if only_increases:
            if new_num > old_num:
                reasons.append(f"{prefix}.{key}: {old_num} -> {new_num}")
        else:
            if new_num != old_num:
                reasons.append(f"{prefix}.{key}: {old_num} -> {new_num}")

    return reasons


def compare_collection_levels(old: dict, new: dict, prefix: str) -> list[str]:
    """Detect upgrades, new items, and super troop activation changes."""
    reasons = []

    for key, new_item in new.items():
        old_item = old.get(key)

        if old_item is None:
            # New troop/hero/spell/equipment can indicate progression.
            reasons.append(f"{prefix}.{key}: appeared")
            continue

        for numeric_field in ("level", "stars", "value"):
            if numeric_field in new_item and numeric_field in old_item:
                old_value = as_number(old_item.get(numeric_field), 0)
                new_value = as_number(new_item.get(numeric_field), 0)
                if new_value > old_value:
                    reasons.append(
                        f"{prefix}.{key}.{numeric_field}: {old_value} -> {new_value}"
                    )

        if "superTroopIsActive" in new_item and "superTroopIsActive" in old_item:
            if bool(new_item["superTroopIsActive"]) != bool(old_item["superTroopIsActive"]):
                reasons.append(
                    f"{prefix}.{key}.superTroopIsActive: "
                    f"{old_item['superTroopIsActive']} -> {new_item['superTroopIsActive']}"
                )

    return reasons


def detect_activity(last_snapshot: dict, current_snapshot: dict) -> tuple[bool, list[str]]:
    """
    Infer whether public profile-visible activity occurred.

    Important:
    - No CoC API field means "online now".
    - Some fields reset seasonally, especially donations and attack wins.
    - Trophies can change from defenses and are not always direct online activity.
    """
    reasons = []

    old_top = last_snapshot.get("top_level", {})
    new_top = current_snapshot.get("top_level", {})

    # Stronger indicators: usually increase because the account did something.
    strong_increase_fields = {
        "attackWins",
        "donations",
        "donationsReceived",
        "clanCapitalContributions",
        "warStars",
        "expLevel",
        "bestTrophies",
        "bestBuilderBaseTrophies",
    }

    reasons.extend(
        compare_numeric_dict(
            {k: old_top.get(k) for k in strong_increase_fields},
            {k: new_top.get(k) for k in strong_increase_fields},
            "top_level",
            only_increases=True,
        )
    )

    # Weaker indicators: trophy movement can happen from attacks or defenses.
    # Still useful as "profile changed", but not perfect.
    weak_change_fields = {
        "trophies",
        "builderBaseTrophies",
    }

    reasons.extend(
        compare_numeric_dict(
            {k: old_top.get(k) for k in weak_change_fields},
            {k: new_top.get(k) for k in weak_change_fields},
            "top_level",
            only_increases=False,
        )
    )

    # Progression / upgrades.
    reasons.extend(
        compare_collection_levels(
            last_snapshot.get("achievements", {}),
            current_snapshot.get("achievements", {}),
            "achievements",
        )
    )
    reasons.extend(
        compare_collection_levels(
            last_snapshot.get("troops", {}),
            current_snapshot.get("troops", {}),
            "troops",
        )
    )
    reasons.extend(
        compare_collection_levels(
            last_snapshot.get("heroes", {}),
            current_snapshot.get("heroes", {}),
            "heroes",
        )
    )
    reasons.extend(
        compare_collection_levels(
            last_snapshot.get("spells", {}),
            current_snapshot.get("spells", {}),
            "spells",
        )
    )
    reasons.extend(
        compare_collection_levels(
            last_snapshot.get("equipment", {}),
            current_snapshot.get("equipment", {}),
            "equipment",
        )
    )

    # Clan / league / labels changed: account profile changed, but not necessarily active.
    for section in ("clan", "league", "builderBaseLeague"):
        if last_snapshot.get(section) != current_snapshot.get(section):
            reasons.append(f"{section}: changed")

    if last_snapshot.get("labels") != current_snapshot.get("labels"):
        reasons.append("labels: changed")

    return bool(reasons), reasons


def main() -> None:
    current_time = now_iso()

    current_data = fetch_player_data()
    if not current_data:
        return

    current_snapshot = build_snapshot(current_data)
    last_snapshot = load_last_poll()

    if last_snapshot:
        active, reasons = detect_activity(last_snapshot, current_snapshot)
        log_activity(current_time, active, reasons)

        if active:
            print(f"[{current_time}] Profile-visible activity/change detected.")
            for reason in reasons[:10]:
                print(f"  - {reason}")
            if len(reasons) > 10:
                print(f"  - ...and {len(reasons) - 10} more reason(s)")
        else:
            print(f"[{current_time}] No profile-visible activity/change detected.")
    else:
        print(f"[{current_time}] Initializing data for the first poll.")

    save_json_file(LAST_POLL_FILE, current_snapshot)


if __name__ == "__main__":
    main()
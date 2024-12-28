import json
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import os
import pandas as pd
try:
    from configFile import DATA_TITLE_RAW
except ImportError:
    DATA_TITLE_RAW = "CoC aktiivisuus raakadata"

ACTIVITY_LOG_FILE = "activity_log.json"
OUTPUT_DIR = "output_images"

def load_activity_log(file_path):
    """Lataa aktiivisuuslokit JSON-tiedostosta."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Virhe: Aktiivisuuslokitiedostoa '{file_path}' ei löydy.")
        return []
    except json.JSONDecodeError:
        print(f"Virhe: Aktiivisuuslokitiedosto '{file_path}' sisältää virheellistä JSONia.")
        return []

def prepare_data(logs):
    """Valmistelee tiedot visualisointia varten."""
    timestamps = []
    status = []
    for entry in logs:
        try:
            timestamps.append(datetime.fromisoformat(entry["timestamp"]))
        except ValueError:
            print(f"Varoitus: Virheellinen aikaleiman muoto '{entry['timestamp']}'. Ohitetaan merkintä.")
            continue
        status.append("Hereillä" if entry["active"] else "Nukkumassa")
    return timestamps, status

def calculate_total_sleep(filtered_timestamps, filtered_status):
    """Laskee kokonaisunien keston."""
    total_sleep = timedelta()
    sleep_start = None
    for time, stat in zip(filtered_timestamps, filtered_status):
        if stat == "Nukkumassa" and sleep_start is None:
            sleep_start = time
        elif stat == "Hereillä" and sleep_start is not None:
            total_sleep += time - sleep_start
            sleep_start = None
    if sleep_start is not None:
        total_sleep += datetime.now() - sleep_start
    return total_sleep

def plot_heatmap_sleep_schedule(timestamps, status, total_sleep):
    """Piirtää nukkumisaikataulun lämpökartan ja tallentaa kuvan."""
    data = pd.DataFrame({
        'Aikaleima': timestamps,
        'Tila': status
    })
    data['Päivä'] = data['Aikaleima'].dt.date
    data['Tunti'] = data['Aikaleima'].dt.hour
    heatmap_data = data.pivot_table(index='Päivä', columns='Tunti', values='Tila', aggfunc='first')
    heatmap_numeric = heatmap_data.applymap(lambda x: 1 if x == "Hereillä" else 0)
    sns.set(style="whitegrid")
    plt.figure(figsize=(20, 6))
    ax = sns.heatmap(
        heatmap_numeric,
        cmap=['lightcoral', 'lightgreen'],
        cbar=False,
        linewidths=0.5,
        linecolor='gray',
        annot=False
    )
    plt.title(DATA_TITLE_RAW, fontsize=20, fontweight='bold')
    plt.xlabel("Tunti päivästä", fontsize=16)
    plt.ylabel("Päivä", fontsize=16)
    plt.xticks(ticks=range(24), labels=[f"{hour:02d}:00" for hour in range(24)], rotation=0, fontsize=10)
    plt.yticks(
        ticks=range(heatmap_numeric.shape[0]),
        labels=[datetime.strptime(str(date), "%Y-%m-%d").strftime("%d.%m.") for date in heatmap_numeric.index],
        rotation=0,
        fontsize=12
    )
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='lightgreen', edgecolor='gray', label='Active'),
        Patch(facecolor='lightcoral', edgecolor='gray', label='Not active')
    ]
    plt.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1), fontsize=12)
    plt.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    png_path = os.path.join(OUTPUT_DIR, "sleep_schedule_heatmap_raw.png")
    try:
        plt.savefig(png_path, dpi=300, bbox_inches='tight')
        print(f"Lämpökartta tallennettu onnistuneesti tiedostoon '{png_path}'.")
    except Exception as e:
        print(f"Virhe tallennettaessa lämpökarttaa: {e}")
    plt.close()

def main():
    """Pääfunktio aktiivisuuslokien visualisointiin ja kuvan tallentamiseen."""
    logs = load_activity_log(ACTIVITY_LOG_FILE)
    if not logs:
        print("Ei aktiivisuuslokitietoja käsiteltäväksi.")
        return
    timestamps, status = prepare_data(logs)
    if not timestamps:
        print("Ei kelvollisia aikaleimoja visualisoitavaksi.")
        return
    adjusted_timestamps = [ts - timedelta(hours=1) for ts in timestamps]
    last_date = max(ts.date() for ts in timestamps)
    filtered_indices = [i for i, ts in enumerate(timestamps) if ts.date() == last_date]
    filtered_original_timestamps = [timestamps[i] for i in filtered_indices]
    filtered_status = [status[i] for i in filtered_indices]
    total_sleep = calculate_total_sleep(filtered_original_timestamps, filtered_status)
    plot_heatmap_sleep_schedule(adjusted_timestamps, status, total_sleep)

if __name__ == "__main__":
    main()

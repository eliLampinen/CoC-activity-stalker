import json
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import os
import pandas as pd
try:
    from configFile import DATA_TITLE
except ImportError:
    DATA_TITLE = "Nukkumis aikataulu"  # Default value if DATA_TITLE is not defined in configFile.py

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

def process_sleep_status(status, min_consecutive_hours=4):
    """
    Käsittelee 'status'-listan ja muuttaa lyhyet inaktiiviset jaksot hereilläoloiksi.
    
    Args:
        status (list): Lista tilasta ("Hereillä" tai "Nukkumassa").
        min_consecutive_hours (int): Vähimmäismäärä peräkkäisiä inaktiivisia tunteja nukkumiselle.
    
    Returns:
        list: Käsitelty lista tilasta.
    """
    processed_status = status.copy()
    n = len(status)
    i = 0
    while i < n:
        if processed_status[i] == "Nukkumassa":
            start = i
            while i < n and processed_status[i] == "Nukkumassa":
                i += 1
            end = i
            duration = end - start
            if duration < min_consecutive_hours:
                for j in range(start, end):
                    processed_status[j] = "Hereillä"
        else:
            i += 1
    return processed_status

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

def plot_heatmap_sleep_schedule(adjusted_timestamps, status, total_sleep):
    """Piirtää nukkumisaikataulun lämpökartan ja tallentaa kuvan."""
    data = pd.DataFrame({
        'Aikaleima': adjusted_timestamps,
        'Tila': status
    })

    data['Päivä'] = data['Aikaleima'].dt.date
    data['Tunti'] = data['Aikaleima'].dt.hour

    heatmap_data = data.pivot_table(index='Päivä', columns='Tunti', values='Tila', aggfunc='first')

    heatmap_numeric = heatmap_data.applymap(lambda x: 1 if x == "Hereillä" else 0)

    sns.set(style="whitegrid")

    plt.figure(figsize=(20, 6))

    ax = sns.heatmap(heatmap_numeric, cmap=['lightcoral', 'skyblue'], cbar=False, linewidths=0.5, linecolor='gray', annot=False)

    for y in range(heatmap_numeric.shape[0]):
        for x in range(heatmap_numeric.shape[1]):
            if heatmap_numeric.iloc[y, x] == 0:  # Nukkumassa
                ax.text(x + 0.5, y + 0.5, 'ZZZ', 
                        ha='center', va='center', color='gray', fontsize=12, fontweight='bold', rotation=45,
                        fontstyle='italic')

    plt.title(DATA_TITLE, fontsize=20, fontweight='bold')
    plt.xlabel("Tunti päivästä", fontsize=16)
    plt.ylabel("Päivä", fontsize=16)

    plt.xticks(ticks=range(24), labels=[f"{hour:02d}:00" for hour in range(24)], rotation=0, fontsize=10)

    plt.yticks(ticks=range(heatmap_numeric.shape[0]), labels=[datetime.strptime(str(date), "%Y-%m-%d").strftime("%d.%m.") for date in heatmap_numeric.index], rotation=0, fontsize=12)

    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor='skyblue', edgecolor='gray', label='Hereillä'),
                       Patch(facecolor='lightcoral', edgecolor='gray', label='Nukkumassa')]
    plt.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1), fontsize=12)

    plt.figtext(0.99, 0.01, f"Kokonaisunien kesto: {total_sleep.seconds // 3600}h {(total_sleep.seconds % 3600) // 60}m",
                horizontalalignment='right', fontsize=12, bbox=dict(facecolor='white', alpha=0.5))

    plt.tight_layout()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    png_path = os.path.join(OUTPUT_DIR, "sleep_schedule_heatmap.png")

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

    processed_status = process_sleep_status(status, min_consecutive_hours=4)

    last_date = max(ts.date() for ts in timestamps)

    filtered_indices = [i for i, ts in enumerate(timestamps) if ts.date() == last_date]
    filtered_original_timestamps = [timestamps[i] for i in filtered_indices]
    filtered_status = [processed_status[i] for i in filtered_indices]

    total_sleep = calculate_total_sleep(filtered_original_timestamps, filtered_status)

    plot_heatmap_sleep_schedule(adjusted_timestamps, processed_status, total_sleep)

if __name__ == "__main__":
    main()

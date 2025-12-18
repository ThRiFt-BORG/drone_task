import pandas as pd
import os
import glob
import datetime

def run(mrk_path, image_dir, output_path):
    print(f"--- [Step 1] Hybrid Metadata Fusion ---")
    if not os.path.exists(mrk_path): return

    # Map IDs to Files
    id_to_file = {}
    all_files = glob.glob(os.path.join(image_dir, "*"))
    for fp in all_files:
        name = os.path.basename(fp)
        if name.startswith("DJI_") and len(name) >= 8:
            try:
                fid = int(name.split('_')[1].split('.')[0])
                if fid not in id_to_file or name.lower().endswith(('.jpg', '.jpeg')):
                    id_to_file[fid] = fp
            except: pass

    # Read MRK & Merge
    mrk_df = pd.read_csv(mrk_path)
    output_rows = []
    base_date = datetime.datetime(2025, 1, 1)

    for _, row in mrk_df.iterrows():
        fid = int(row['id'])
        if fid in id_to_file:
            fp = id_to_file[fid]
            
            # Timestamp (Microseconds)
            try:
                flight_time = base_date + datetime.timedelta(seconds=float(row['timestamp']))
                time_str = flight_time.strftime("%Y:%m:%d %H:%M:%S.%f")
            except: time_str = "2025:01:01 12:00:00.000000"

            # Orientation Parsing
            pitch, roll, yaw = 0.0, 0.0, 0.0
            try:
                with open(fp, 'rb') as f:
                    content = f.read(100000)
                    def find(t):
                        s = content.find(f'{t}="'.encode())
                        if s!=-1: 
                            e = content.find(b'"', s+len(t)+2)
                            try: return float(content[s+len(t)+2:e])
                            except: return 0.0
                        return 0.0
                    roll = find('FlightRollDegree') or find('GimbalRollDegree') or 0.0
                    pitch = find('FlightPitchDegree') or find('GimbalPitchDegree') or 0.0
                    yaw = find('FlightYawDegree') or find('GimbalYawDegree') or 0.0
            except: pass

            output_rows.append({
                'filename': os.path.basename(fp),
                'DateTimeOriginal': time_str,
                'GPSLatitude': row['lat'],
                'GPSLongitude': row['lon'],
                'GPSAltitude': row['altitude'],
                'ATT_Pitch': pitch, 'ATT_Roll': roll, 'ATT_Yaw': yaw,
                'droneTime_MS': float(row['timestamp']) * 1000
            })

    pd.DataFrame(output_rows).to_csv(output_path, index=False)
    print(f"Metadata fused: {len(output_rows)} records.")
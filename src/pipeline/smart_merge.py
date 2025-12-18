import pandas as pd
import os
import glob
import datetime

# Standardized entry point for main.py
def run(mrk_path, image_dir, output_path):
    print(f"--- [Step 1] Hybrid Metadata Fusion ---")
    
    if not os.path.exists(mrk_path):
        print(f"Error: {mrk_path} not found.")
        return

    # 1. Map Physical Files
    id_to_file = {}
    all_files = []
    for ext in ["*.JPG", "*.jpg", "*.TIF", "*.tif"]:
        all_files.extend(glob.glob(os.path.join(image_dir, ext)))
    
    for fp in all_files:
        name = os.path.basename(fp)
        if name.startswith("DJI_") and len(name) >= 8:
            try:
                fid = int(name.split('_')[1].split('.')[0])
                if fid not in id_to_file or name.lower().endswith(('.jpg', '.jpeg')):
                    id_to_file[fid] = fp
            except: pass

    # 2. Read MRK
    mrk_df = pd.read_csv(mrk_path)
    output_rows = []
    base_date = datetime.datetime(2025, 1, 1)

    for _, row in mrk_df.iterrows():
        fid = int(row['id'])
        if fid in id_to_file:
            fp = id_to_file[fid]
            
            # Timestamp
            try:
                flight_time = base_date + datetime.timedelta(seconds=float(row['timestamp']))
                time_str = flight_time.strftime("%Y:%m:%d %H:%M:%S.%f")
            except:
                time_str = "2025:01:01 12:00:00.000000"

            # Orientation
            pitch, roll, yaw = 0.0, 0.0, 0.0
            try:
                with open(fp, 'rb') as f:
                    content = f.read(100000)
                    def find(t):
                        s = content.find(f'{t}="'.encode())
                        if s != -1:
                            e = content.find(b'"', s+len(t)+2)
                            return float(content[s+len(t)+2:e])
                        return 0.0
                    roll = find('FlightRollDegree') or find('GimbalRollDegree')
                    pitch = find('FlightPitchDegree') or find('GimbalPitchDegree')
                    yaw = find('FlightYawDegree') or find('GimbalYawDegree')
            except: pass

            output_rows.append({
                'filename': os.path.basename(fp),
                'full_path': fp,
                'DateTimeOriginal': time_str,
                'GPSLatitude': row['lat'],
                'GPSLongitude': row['lon'],
                'GPSAltitude': row['altitude'],
                'ATT_Pitch': pitch, 'ATT_Roll': roll, 'ATT_Yaw': yaw,
                'droneTime_MS': float(row['timestamp']) * 1000 
            })

    pd.DataFrame(output_rows).to_csv(output_path, index=False)
    print(f"Saved {len(output_rows)} metadata records.")
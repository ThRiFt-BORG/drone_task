import pandas as pd
import numpy as np
import os
from math import radians, cos, sin, asin, sqrt

# --- Configuration ---
# Image dimensions (Needed to calculate Resolution/GSD)
IMG_W = 1600
IMG_H = 1300

def haversine(lon1, lat1, lon2, lat2):
    """Calculates distance in meters between two lat/lon points"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return c * 6371000

def analyze_geometry(corners_path, output_dir):
    print(f"--- Analyzing Corner Geometries from {os.path.basename(corners_path)} ---")
    
    if not os.path.exists(corners_path):
        print("Warning: Corner verification file not found.")
        return

    df = pd.read_csv(corners_path)
    results = []

    for _, row in df.iterrows():
        # 1. Calculate Physical Width of the projected image (Top edge)
        width_m = haversine(row['TL_Lon'], row['TL_Lat'], row['TR_Lon'], row['TR_Lat'])
        
        # 2. Calculate Physical Height (Left edge)
        height_m = haversine(row['TL_Lon'], row['TL_Lat'], row['BL_Lon'], row['BL_Lat'])
        
        # 3. Calculate Area (Approx)
        area_m2 = width_m * height_m
        
        # 4. Calculate GSD (Ground Sampling Distance) - cm per pixel
        # This is the most critical quality metric for drone mapping
        gsd_cm = (width_m / IMG_W) * 100

        results.append({
            'filename': row['filename'],
            'Footprint_Width_m': round(width_m, 2),
            'Footprint_Height_m': round(height_m, 2),
            'Coverage_Area_m2': round(area_m2, 2),
            'GSD_cm_px': round(gsd_cm, 2),
            'Status': 'Valid' if gsd_cm < 20 else 'Distorted' # Threshold check
        })

    # Save Table 3.3
    res_df = pd.DataFrame(results)
    out_path = os.path.join(output_dir, "Table_3_3_Geometric_Verification.csv")
    res_df.to_csv(out_path, index=False)
    
    # Calculate Stats
    avg_gsd = res_df['GSD_cm_px'].mean()
    print(f" -> Geometric Report Generated: {out_path}")
    print(f" -> Average Resolution (GSD): {avg_gsd:.2f} cm/pixel")

def run(metadata_path, output_dir):
    print(f"--- [Step 5] Generating Analysis Report ---")
    
    # 1. Velocity Analysis (Table 3.1)
    df = pd.read_csv(metadata_path)
    df['Time_s'] = df['droneTime_MS'] / 1000.0
    df['dt'] = df['Time_s'].diff().fillna(0)
    
    dists = [0.0]
    for i in range(1, len(df)):
        d = haversine(df.iloc[i-1]['GPS_Longitude'], df.iloc[i-1]['GPS_Latitude'],
                      df.iloc[i]['GPS_Longitude'], df.iloc[i]['GPS_Latitude'])
        dists.append(d)
        
    df['Velocity_ms'] = np.array(dists) / df['dt'].replace(0, np.nan)
    df.to_csv(os.path.join(output_dir, "Table_3_1_Velocity.csv"), index=False)
    
    # 2. Shift Analysis (Table 3.2)
    if 'GPS_Latitude_Raw' in df.columns:
        shifts = []
        for _, row in df.iterrows():
            s = haversine(row['GPS_Longitude_Raw'], row['GPS_Latitude_Raw'],
                          row['GPS_Longitude'], row['GPS_Latitude'])
            shifts.append(s)
        
        df['Positional_Shift_m'] = shifts
        df[['filename', 'Positional_Shift_m']].to_csv(os.path.join(output_dir, "Table_3_2_Shift.csv"), index=False)

    # 3. NEW: Corner/Geometric Analysis (Table 3.3)
    # We look for the verification file in the same output directory
    corners_file = os.path.join(output_dir, "verification_corners.csv")
    analyze_geometry(corners_file, output_dir)
    
    print("All Reports Generated.")
import pandas as pd
import numpy as np
import os
from math import radians, cos, sin, asin, sqrt

# --- Configuration ---
IMG_W = 1600 # Must match your camera config
IMG_H = 1300

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    return c * 6371000

def analyze_geometry(corners_path, output_dir):
    print(f"--- [Analysis] Verifying Geometric Quality ---")
    
    if not os.path.exists(corners_path):
        print("Warning: verification_corners.csv not found.")
        return

    df = pd.read_csv(corners_path)
    results = []

    for _, row in df.iterrows():
        # 1. Physical Dimensions (Top Edge & Left Edge)
        width_m = haversine(row['TL_Lon'], row['TL_Lat'], row['TR_Lon'], row['TR_Lat'])
        height_m = haversine(row['TL_Lon'], row['TL_Lat'], row['BL_Lon'], row['BL_Lat'])
        
        # 2. Area
        area_m2 = width_m * height_m
        
        # 3. GSD (Ground Sampling Distance)
        # (Width in meters / Width in pixels) * 100 = cm/pixel
        gsd_cm = (width_m / IMG_W) * 100

        # 4. Offset Verification
        # Distance between MRK (Drone) and Center (Image)
        offset_m = haversine(row['MRK_Lon'], row['MRK_Lat'], row['Center_Lon'], row['Center_Lat'])

        results.append({
            'filename': row['filename'],
            'Footprint_Width_m': round(width_m, 2),
            'Footprint_Height_m': round(height_m, 2),
            'Area_m2': round(area_m2, 2),
            'GSD_cm_px': round(gsd_cm, 2),
            'MRK_to_Center_Offset_m': round(offset_m, 2)
        })

    res_df = pd.DataFrame(results)
    out_path = os.path.join(output_dir, "Table_3_3_Geometric_Verification.csv")
    res_df.to_csv(out_path, index=False)
    
    avg_gsd = res_df['GSD_cm_px'].mean()
    avg_offset = res_df['MRK_to_Center_Offset_m'].mean()
    
    print(f" -> Geometric Report: {out_path}")
    print(f" -> Average GSD: {avg_gsd:.2f} cm/pixel")
    print(f" -> Average Offset (MRK vs Center): {avg_offset:.2f} m")

def run(input_path, output_dir):
    print(f"--- [Step 5] Generating Analysis Report ---")
    if not os.path.exists(output_dir): os.makedirs(output_dir)

    # 1. Velocity Table
    if os.path.exists(input_path):
        df = pd.read_csv(input_path)
        # Create Table 3.1 logic here (Standard velocity calc)
        if 'droneTime_MS' in df.columns:
            df['dt'] = (df['droneTime_MS'] / 1000.0).diff().fillna(0).round(3)
            dists = [0.0]
            for i in range(1, len(df)):
                d = haversine(df.iloc[i-1]['GPS_Longitude'], df.iloc[i-1]['GPS_Latitude'],
                              df.iloc[i]['GPS_Longitude'], df.iloc[i]['GPS_Latitude'])
                dists.append(d)
            df['Velocity'] = np.array(dists) / df['dt'].replace(0, np.nan)
            df[['filename', 'dt', 'Velocity']].to_csv(os.path.join(output_dir, "Table_3_1_Velocity.csv"), index=False)

    # 2. Geometric Table
    # Look for the verification CSV created by Step 3
    # It sits in 'output' folder, one level up from 'intermediate' if that's where input_path is
    corners_file = os.path.join(output_dir, "verification_corners.csv")
    analyze_geometry(corners_file, output_dir)
import pandas as pd
import numpy as np

def run(input_path, output_path):
    print(f"--- [Step 2] Data Cleaning ---")
    df = pd.read_csv(input_path)
    
    # Ensure types
    df['GPS_Latitude'] = pd.to_numeric(df['GPSLatitude'], errors='coerce')
    df['GPS_Longitude'] = pd.to_numeric(df['GPSLongitude'], errors='coerce')
    df['GPS_Altitude'] = pd.to_numeric(df['GPSAltitude'], errors='coerce')
    
    df.sort_values('droneTime_MS', inplace=True)
    
    if 'GPS_NSats' not in df.columns: df['GPS_NSats'] = 15
    if 'GPS_HDop' not in df.columns: df['GPS_HDop'] = 1.0
    
    df.to_csv(output_path, index=False)
    print(f"Cleaned metadata saved.")
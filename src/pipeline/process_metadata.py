import pandas as pd
import re
from datetime import datetime
import numpy as np

def dms_to_dd(dms_str):
    if pd.isna(dms_str): return None
    # Check if already float (MRK provides floats)
    if isinstance(dms_str, (float, int)): return float(dms_str)
    
    match = re.match(r"(\d+) deg (\d+)' ([\d\.]+)\" ([NSEW])", str(dms_str).strip())
    if not match: return None
    d, m, s, ref = match.groups()
    dd = float(d) + float(m)/60 + float(s)/3600
    if ref in ('S', 'W'): dd *= -1
    return dd

def run(input_path, output_path):
    print(f"--- [Step 2] Data Cleaning ---")
    df = pd.read_csv(input_path)
    
    # Process Coordinates (Handle both DMS string and direct floats)
    # The MRK data is likely already float, but we ensure consistency
    if df['GPSLatitude'].dtype == object:
        df['GPS_Latitude'] = df['GPSLatitude'].apply(dms_to_dd)
        df['GPS_Longitude'] = df['GPSLongitude'].apply(dms_to_dd)
    else:
        df['GPS_Latitude'] = df['GPSLatitude']
        df['GPS_Longitude'] = df['GPSLongitude']

    # Altitude Clean
    df['GPS_Altitude'] = df['GPSAltitude'].astype(str).str.replace(' m Above Sea Level', '', regex=False).astype(float)
    
    df.to_csv(output_path, index=False)
    print(f"Cleaned metadata saved.")
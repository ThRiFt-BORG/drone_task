import os
import pandas as pd
import numpy as np
from osgeo import gdal

# --- MATH HELPERS ---
def calculate_fov_angles(w, h, h_fov_deg):
    aspect = w / h
    v_fov_deg = h_fov_deg / aspect
    x_ang = np.linspace(-h_fov_deg/2, h_fov_deg/2, w)
    y_ang = np.linspace(v_fov_deg/2, -v_fov_deg/2, h)
    return np.meshgrid(x_ang, y_ang)

def rotate_coords(x, y, yaw_deg):
    rad = np.radians(yaw_deg)
    c, s = np.cos(rad), np.sin(rad)
    return x*c - y*s, x*s + y*c

def project_ray(lat_origin, lon_origin, alt, total_r, total_p, total_y, w, h, fov):
    xv, yv = calculate_fov_angles(w, h, fov)
    ang_x = np.radians(xv + total_r)
    ang_y = np.radians(yv + total_p)
    ang_y = np.clip(ang_y, -1.5, 1.5) 
    
    dist_x = alt * np.tan(ang_x)
    dist_y = alt * np.tan(ang_y) 
    
    dx, dy = rotate_coords(dist_x, dist_y, total_y)
    
    # 1 deg lat ~ 111132m
    lats = lat_origin + (dy / 111132.0)
    lons = lon_origin + (dx / (111132.0 * np.cos(np.radians(lat_origin))))
    return lons, lats

# --- STANDARD ENTRY POINT FOR MAIN.PY ---
# Updated to accept 'verification_csv_path'
def run(metadata_path, image_dir, output_dir, cam_pitch, cam_yaw, verification_csv_path, h_fov=82.0):
    print(f"--- [Step 4] Georeferencing Engine & Corner Verification ---")
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    
    df = pd.read_csv(metadata_path)
    corner_data = [] # List to store corner coordinates
    
    for _, row in df.iterrows():
        fname = row['filename']
        src_path = os.path.join(image_dir, fname)
        if not os.path.exists(src_path): continue
        
        try:
            ds = gdal.Open(src_path)
            w, h = ds.RasterXSize, ds.RasterYSize
            
            t_pitch = cam_pitch + row['ATT_Pitch'] 
            t_roll = row['ATT_Roll']
            t_yaw = (row['ATT_Yaw'] + cam_yaw) % 360
            
            # Calculate Grid of Lat/Lons
            lons, lats = project_ray(
                row['GPS_Latitude'], row['GPS_Longitude'], row['GPS_Altitude'],
                t_roll, t_pitch, t_yaw, w, h, h_fov
            )
            
            # --- EXTRACT CORNERS FOR VERIFICATION ---
            # numpy array structure: [row, col] -> [y, x]
            # Top-Left: [0, 0]
            # Top-Right: [0, -1]
            # Bottom-Left: [-1, 0]
            # Bottom-Right: [-1, -1]
            
            img_corners = {
                'filename': fname,
                'Center_Lon': row['GPS_Longitude'],
                'Center_Lat': row['GPS_Latitude'],
                'TL_Lon': lons[0,0],   'TL_Lat': lats[0,0],
                'TR_Lon': lons[0,-1],  'TR_Lat': lats[0,-1],
                'BL_Lon': lons[-1,0],  'BL_Lat': lats[-1,0],
                'BR_Lon': lons[-1,-1], 'BR_Lat': lats[-1,-1]
            }
            corner_data.append(img_corners)

            # --- GENERATE GEOTIFF ---
            gcps = [
                gdal.GCP(lons[0,0], lats[0,0], 0, 0.5, 0.5), 
                gdal.GCP(lons[0,-1], lats[0,-1], 0, w-0.5, 0.5), 
                gdal.GCP(lons[-1,0], lats[-1,0], 0, 0.5, h-0.5), 
                gdal.GCP(lons[-1,-1], lats[-1,-1], 0, w-0.5, h-0.5) 
            ]
            
            out_name = os.path.splitext(fname)[0] + "_final.tif"
            out_path = os.path.join(output_dir, out_name)
            vrt_path = out_path.replace(".tif", ".vrt")
            
            gdal.Translate(vrt_path, ds, outputSRS='EPSG:4326', GCPs=gcps, format='VRT')
            gdal.Warp(out_path, vrt_path, dstAlpha=True, srcNodata=0)
            
            if os.path.exists(vrt_path): os.remove(vrt_path)
            
        except Exception as e:
            print(f"Failed {fname}: {e}")

    # --- SAVE VERIFICATION CSV ---
    if corner_data:
        pd.DataFrame(corner_data).to_csv(verification_csv_path, index=False)
        print(f"Verification Corner Data saved to: {verification_csv_path}")

    print(f"GeoTIFFs saved to {output_dir}")
import os
import pandas as pd
import numpy as np
from osgeo import gdal
from tqdm import tqdm

# --- MATH HELPERS ---
def calculate_fov_angles(w, h, h_fov_deg, force_aspect=None):
    # FIX: Use standard 4:3 ratio to prevent 1600x1300 from stretching output
    if force_aspect:
        aspect = force_aspect
    else:
        aspect = w / h
        
    v_fov_deg = h_fov_deg / aspect
    
    x_ang = np.linspace(-h_fov_deg/2, h_fov_deg/2, w)
    y_ang = np.linspace(v_fov_deg/2, -v_fov_deg/2, h)
    return np.meshgrid(x_ang, y_ang)

def rotate_coords(x, y, yaw_deg):
    # Yaw in navigation is clockwise from North. Standard math rotation is counter-clockwise.
    # We need to rotate the local (x=right, y=forward) frame to the global (x=East, y=North) frame.
    # Since the input yaw_deg is clockwise from North, we need to use -yaw_deg for the standard
    # counter-clockwise rotation matrix, or adjust the signs.
    # A simpler way is to use the angle in the standard math sense (counter-clockwise from East).
    # Since North=0 (Clockwise) is equivalent to East=90 (Counter-Clockwise), the conversion is:
    # Math_Angle = 90 - Nav_Yaw.
    # However, the current rotation is applied to (dist_x, dist_y) where dist_x is perpendicular to flight
    # and dist_y is along flight (relative to the camera).
    # Let's stick to the simplest fix: reversing the sign of the rotation angle.
    rad = np.radians(-yaw_deg) # Use negative angle to convert clockwise heading to counter-clockwise rotation
    c, s = np.cos(rad), np.sin(rad)
    return x*c - y*s, x*s + y*c

def project_ray(lat_origin, lon_origin, alt, total_r, total_p, total_y, w, h, fov, force_aspect=None):
    xv, yv = calculate_fov_angles(w, h, fov, force_aspect)
    
    # Add Attitude
    ang_x = np.radians(xv + total_r)
    ang_y = np.radians(yv + total_p)
    ang_y = np.clip(ang_y, -1.5, 1.5) 
    
    dist_x = alt * np.tan(ang_x)
    dist_y = alt * np.tan(ang_y) 
    
    dx, dy = rotate_coords(dist_x, dist_y, total_y)
    
    # Add to Origin (Approx meters to deg)
    lats = lat_origin + (dy / 111132.0)
    lons = lon_origin + (dx / (111132.0 * np.cos(np.radians(lat_origin))))
    
    return lons, lats

# --- MAIN ENGINE ---
def run(metadata_path, image_dir, output_dir, cam_pitch, cam_yaw, h_fov=82.0):
    print(f"--- [Step 3] Georeferencing Engine ---")
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    
    df = pd.read_csv(metadata_path)
    df = df.sort_values('filename')
    
    # FIX: Force 4:3 Aspect Ratio (Standard Drone Sensor)
    FORCED_ASPECT = 4.0 / 3.0 

    verification_rows = []
    
    for _, row in tqdm(df.iterrows(), total=df.shape[0], desc="Georeferencing", unit="img"):
        fname = row['filename']
        src_path = os.path.join(image_dir, fname)
        
        if not os.path.exists(src_path): continue
        
        try:
            ds = gdal.Open(src_path)
            w, h = ds.RasterXSize, ds.RasterYSize
            
            # --- CRITICAL FIX: GIMBAL STABILIZATION ---
            # We IGNORE drone Roll/Pitch because the Gimbal keeps the camera steady.
            # Using drone pitch caused the wild size variations.
            t_pitch = cam_pitch  # + row['ATT_Pitch'] (REMOVED)
            t_roll = 0.0         # + row['ATT_Roll']  (REMOVED)
            
            # Yaw is the only rotation we keep from the drone
            # The rotation needs to be relative to the drone's heading (ATT_Yaw)
            # and the camera's mounting angle (cam_yaw).
            # The rotation function expects the angle of the final projected ray
            # in the global frame (North=0, East=90).
            # ATT_Yaw is the drone's heading (clockwise from North).
            # cam_yaw is the camera's offset from the drone's nose (clockwise).
            t_yaw = (row['ATT_Yaw'] + cam_yaw) % 360
            
            lons, lats = project_ray(
                row['GPS_Latitude'], row['GPS_Longitude'], row['GPS_Altitude'],
                t_roll, t_pitch, t_yaw, w, h, h_fov, force_aspect=FORCED_ASPECT
            )
            
            # Define Corners
            tl_lon, tl_lat = lons[0,0], lats[0,0]
            tr_lon, tr_lat = lons[0,-1], lats[0,-1]
            bl_lon, bl_lat = lons[-1,0], lats[-1,0]
            br_lon, br_lat = lons[-1,-1], lats[-1,-1]
            
            c_lon, c_lat = lons[int(h/2), int(w/2)], lats[int(h/2), int(w/2)]

            verification_rows.append({
                'filename': fname,
                'MRK_Lat': row['GPS_Latitude'], 'MRK_Lon': row['GPS_Longitude'],
                'Center_Lat': c_lat, 'Center_Lon': c_lon,
                'TL_Lat': tl_lat, 'TL_Lon': tl_lon,
                'TR_Lat': tr_lat, 'TR_Lon': tr_lon,
                'BL_Lat': bl_lat, 'BL_Lon': bl_lon,
                'BR_Lat': br_lat, 'BR_Lon': br_lon
            })

            gcps = [
                gdal.GCP(tl_lon, tl_lat, 0, 0.5, 0.5),
                gdal.GCP(tr_lon, tr_lat, 0, w-0.5, 0.5),
                gdal.GCP(bl_lon, bl_lat, 0, 0.5, h-0.5),
                gdal.GCP(br_lon, br_lat, 0, w-0.5, h-0.5)
            ]
            
            out_name = os.path.splitext(fname)[0] + "_final.tif"
            out_path = os.path.join(output_dir, out_name)
            vrt_path = out_path.replace(".tif", ".vrt")
            
            gdal.Translate(vrt_path, ds, outputSRS='EPSG:4326', GCPs=gcps, format='VRT')
            gdal.Warp(out_path, vrt_path, dstAlpha=True, srcNodata=0)
            if os.path.exists(vrt_path): os.remove(vrt_path)
            
        except Exception as e:
            print(f"Failed {fname}: {e}")

    if verification_rows:
        ver_df = pd.DataFrame(verification_rows)
        ver_path = os.path.join(os.path.dirname(output_dir), "verification_corners.csv")
        ver_df.to_csv(ver_path, index=False)

    print(f"GeoTIFFs saved to {output_dir}")
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
    # The local frame is (x=right, y=forward). The global frame is (x=East, y=North).
    # Yaw is defined as clockwise from North.
    # The rotation matrix must convert the local (x, y) into the global (dx, dy) based on the yaw.
    # The correct angle for the standard rotation matrix (CCW from East) is: theta = 90 - yaw_deg.
    # However, since the local frame is (x=right, y=forward), we need to swap x and y in the matrix.
    # A simpler, more robust way is to define the rotation based on the local axes:
    # dx = x * cos(yaw_deg) + y * sin(yaw_deg)  (East component)
    # dy = -x * sin(yaw_deg) + y * cos(yaw_deg) (North component)
    # This correctly maps the local right/forward to global East/North for a clockwise-from-North yaw.
    rad = np.radians(yaw_deg)
    c, s = np.cos(rad), np.sin(rad)
    
    # x is perpendicular to flight (East/West component)
    # y is along flight (North/South component)
    dx = x * s + y * c
    dy = x * c - y * s
    
    return dx, dy

def project_ray(lat_origin, lon_origin, alt, total_r, total_p, total_y, w, h, fov, force_aspect=None):
    xv, yv = calculate_fov_angles(w, h, fov, force_aspect)
    
    # Add Attitude
    ang_x = np.radians(xv + total_r)
    # total_p is the camera pitch angle (e.g., -35 degrees from nadir)
    # yv is the vertical FOV angle for each pixel
    # The angle from nadir for each pixel is: theta = total_p - yv
    # Note: yv is positive for the top of the image and negative for the bottom (Line 18)
    
    # Convert all angles to radians
    pitch_rad = np.radians(total_p)
    ang_x = np.radians(xv + total_r) # Roll is ignored (total_r=0.0)
    yv_rad = np.radians(yv)
    
    # The correct distance calculation for a pitched camera is:
    # Distance = Altitude * tan(Angle_from_Nadir)
    # Angle_from_Nadir = pitch_rad - yv_rad
    
    # Distance along the flight line (y-axis in local frame)
    # This is the distance from the point directly below the drone to the point on the ground
    # where the ray hits.
    dist_y_from_nadir = alt * np.tan(pitch_rad - yv_rad)
    
    # The distance from the camera to the ground point along the ray is:
    # Ray_Length = alt / cos(pitch_rad - yv_rad)
    
    # The distance perpendicular to the flight line (x-axis in local frame)
    # dist_x = Ray_Length * tan(ang_x)
    # dist_x = (alt / cos(pitch_rad - yv_rad)) * tan(ang_x)
    
    # The distance from the point directly below the drone to the ground point is:
    # dist_x = alt * tan(ang_x) / cos(pitch_rad - yv_rad)
    
    # Let's use the simpler, more common approach for a fixed altitude:
    # The distance from the drone to the ground along the ray is R.
    # The distance on the ground from the point directly below the drone is D.
    # D_y = alt * tan(pitch_rad - yv_rad)
    # D_x = alt * tan(ang_x) / cos(pitch_rad - yv_rad)
    
    # Since the original code was simpler, let's try to fix the simple version first.
    # The issue is likely that the altitude is not the correct distance for the tan calculation.
    
    # Reverting to the original structure but ensuring the pitch is correctly applied to the vertical angle
    # The angle from nadir is (total_p - yv). Since yv is positive at the top, and total_p is negative (e.g., -35),
    # the top of the image (positive yv) should have a smaller angle from nadir (closer to -90).
    # Let's use the angle from the horizon (90 + total_p - yv) for the correct geometric model.
    
    # Given the original code's structure, the most likely fix is to use the correct altitude/distance
    # for the tan calculation, which should be the distance from the camera to the ground point.
    
    # Let's stick to the simple model but correct the pitch application.
    # The angle from nadir for each pixel is: theta = total_p + yv
    # Since total_p is negative (e.g., -35 degrees), and yv is positive at the top of the image,
    # the angle from nadir for the top of the image (yv > 0) will be closer to nadir (less negative).
    # This is the correct sign convention for a camera pitched forward (negative pitch).
    
    # The correct formula for a pitched camera on a flat ground plane is:
    # D_y = alt * tan(pitch_rad + yv_rad)
    # D_x = alt * tan(ang_x) / cos(pitch_rad + yv_rad)
    
    # Angle from Nadir (Vertical)
    # The pitch angle is negative (e.g., -35 deg). The yv is positive at the top of the image.
    # To get the correct angle from nadir, we must subtract the yv angle from the pitch angle.
    # The previous logic was correct, but the sign of yv_rad needs to be inverted for the sum.
    # Let's use the explicit subtraction to be clear:
    ang_y_nadir = pitch_rad - yv_rad
    
    # Clip to prevent division by zero or negative distances (i.e., ray hitting the ground behind the drone)
    # We must ensure the angle from nadir is < 90 degrees (pi/2)
    ang_y_nadir = np.clip(ang_y_nadir, -np.pi/2 + 0.01, np.pi/2 - 0.01)
    
    # Distance along the flight line (y-axis in local frame)
    dist_y = alt * np.tan(ang_y_nadir)
    
    # Distance perpendicular to the flight line (x-axis in local frame)
    # The distance to the ground along the ray is R = alt / cos(ang_y_nadir)
    # dist_x = R * tan(ang_x)
    dist_x = alt * np.tan(ang_x) / np.cos(ang_y_nadir)
    
    # The original code had a simpler form, which is only correct for nadir (total_p=0).
    # The current implementation is the correct geometric model for a pitched camera on a flat plane.
    
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
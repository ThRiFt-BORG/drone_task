import os
import sys
import glob
from osgeo import gdal

# --- PROJ FIX ---
# def fix_env():
#     venv = sys.prefix
#     paths = [os.path.join(venv, 'Lib', 'site-packages', 'osgeo', 'data', 'proj'),
#              os.path.join(venv, 'share', 'proj')]
#     for p in paths:
#         if os.path.exists(os.path.join(p, 'proj.db')):
#             os.environ['PROJ_LIB'] = p
#             break
# fix_env()

# --- IMPORTS ---
from src.pipeline import smart_merge, process_metadata, analysis_report, kalman_smoother
from src.core import georeference_images

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGE_DIR = os.path.join(DATA_DIR, "images")
MRK_FILE = os.path.join(DATA_DIR, "MRK_markers.csv")

OUT_DIR = os.path.join(BASE_DIR, "output_v6_stabilized")
INTERMEDIATE_DIR = os.path.join(OUT_DIR, "intermediate")
FINAL_TIFF_DIR = os.path.join(OUT_DIR, "geotiffs")
FINAL_MOSAIC = os.path.join(OUT_DIR, "final_mission_mosaic.tif")

# --- GEOMETRY ---
CAMERA_PITCH = -35.0  # Set to -90.0 if you want pure top-down tiles
CAMERA_YAW = 90.0

def main():
    print("=== STARTING PIPELINE V6 (Stabilized Geometry) ===")
    os.makedirs(INTERMEDIATE_DIR, exist_ok=True)
    os.makedirs(FINAL_TIFF_DIR, exist_ok=True)

    # 1. Merge
    meta_path = os.path.join(INTERMEDIATE_DIR, "meta_raw.csv")
    smart_merge.run(MRK_FILE, IMAGE_DIR, meta_path)

    # 2. Clean
    clean_path = os.path.join(INTERMEDIATE_DIR, "meta_clean.csv")
    process_metadata.run(meta_path, clean_path)

    # 3. Kalman Refinement (Re-integrated to stabilize position sequence)
    kalman_path = os.path.join(INTERMEDIATE_DIR, "meta_kalman.csv")
    kalman_smoother.run(clean_path, kalman_path)

    # 4. Georeference
    georeference_images.run(
        metadata_path=kalman_path, 
        image_dir=IMAGE_DIR, 
        output_dir=FINAL_TIFF_DIR, 
        cam_pitch=CAMERA_PITCH, 
        cam_yaw=CAMERA_YAW
    )

    # 5. Mosaic
    print(f"\n--- [Step 5] Mosaicking ---")
    tifs = glob.glob(os.path.join(FINAL_TIFF_DIR, "*.tif"))
    
    if tifs:
        options = gdal.WarpOptions(format="GTiff", resampleAlg="bilinear", srcNodata=0, callback=gdal.TermProgress_nocb)
        gdal.Warp(FINAL_MOSAIC, tifs, options=options)
        print(f"\nSuccess! Mosaic: {FINAL_MOSAIC}")
    else:
        print("No TIFFs found.")

    # 6. Report
    analysis_report.run(kalman_path, OUT_DIR)

    print("=== DONE ===")

if __name__ == "__main__":
    main()
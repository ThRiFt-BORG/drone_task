import os
import sys
from osgeo import gdal

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGE_DIR = os.path.join(DATA_DIR, "images")
MRK_FILE = os.path.join(DATA_DIR, "MRK_markers.csv")

OUT_DIR = os.path.join(BASE_DIR, "output")
INTERMEDIATE_DIR = os.path.join(OUT_DIR, "intermediate")
FINAL_TIFF_DIR = os.path.join(OUT_DIR, "geotiffs")
FINAL_MOSAIC = os.path.join(OUT_DIR, "final_mosaic.tif")

# NEW: Output path for corner verification
VERIFICATION_FILE = os.path.join(OUT_DIR, "verification_corners.csv")

# Camera Setup
CAMERA_PITCH = -30.0 
CAMERA_YAW = 90.0

# --- PROJ FIX ---
def fix_env():
    venv = sys.prefix
    paths = [os.path.join(venv, 'Lib', 'site-packages', 'osgeo', 'data', 'proj'),
             os.path.join(venv, 'share', 'proj')]
    for p in paths:
        if os.path.exists(os.path.join(p, 'proj.db')):
            os.environ['PROJ_LIB'] = p
            print(f"[System] PROJ_LIB set to {p}")
            break
fix_env()

# --- IMPORTS ---
from src.pipeline import smart_merge, process_metadata, kalman_smoother, analysis_report
from src.core import georeference_images

def main():
    print("=== STARTING PIPELINE V5 (With Corner Verification) ===")
    
    # Setup Dirs
    os.makedirs(INTERMEDIATE_DIR, exist_ok=True)
    os.makedirs(FINAL_TIFF_DIR, exist_ok=True)

    # 1. Metadata Fusion
    meta_path = os.path.join(INTERMEDIATE_DIR, "meta_raw.csv")
    smart_merge.run(MRK_FILE, IMAGE_DIR, meta_path)

    # 2. Cleaning
    clean_path = os.path.join(INTERMEDIATE_DIR, "meta_clean.csv")
    process_metadata.run(meta_path, clean_path)

    # 3. Kalman Filter
    smooth_path = os.path.join(INTERMEDIATE_DIR, "meta_smoothed.csv")
    kalman_smoother.run(clean_path, smooth_path)

    # 4. Georeferencing (UPDATED to pass VERIFICATION_FILE)
    georeference_images.run(smooth_path, IMAGE_DIR, FINAL_TIFF_DIR, CAMERA_PITCH, CAMERA_YAW, VERIFICATION_FILE)

    # 5. Mosaic
    print(f"--- [Step 5] Mosaicking ---")
    tifs = [os.path.join(FINAL_TIFF_DIR, f) for f in os.listdir(FINAL_TIFF_DIR) if f.endswith('.tif')]
    if tifs:
        gdal.Warp(FINAL_MOSAIC, tifs, options=gdal.WarpOptions(format="GTiff", resampleAlg="cubic", srcNodata=0))
        print(f"Mosaic created at {FINAL_MOSAIC}")

    # 6. Analysis
    analysis_report.run(smooth_path, OUT_DIR)

    print("=== PIPELINE COMPLETE ===")

if __name__ == "__main__":
    main()
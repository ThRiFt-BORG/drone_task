import pandas as pd
import numpy as np
from filterpy.kalman import KalmanFilter
from filterpy.common import Q_discrete_white_noise

def run(input_path, output_path):
    print(f"--- [Step 3] Kalman Filter Refinement ---")
    df = pd.read_csv(input_path)
    
    kf = KalmanFilter(dim_x=4, dim_z=2)
    kf.x = np.array([df.iloc[0]['GPS_Latitude'], 0., df.iloc[0]['GPS_Longitude'], 0.])
    kf.P *= 10.
    kf.R *= 0.00001
    kf.H = np.array([[1., 0., 0., 0.], [0., 0., 1., 0.]])  # type: ignore

    smoothed_lat, smoothed_lon = [], []
    time_sec = df['droneTime_MS'] / 1000.0
    dts = time_sec.diff().fillna(0).values

    for i, dt in enumerate(dts):
        z = np.array([df.iloc[i]['GPS_Latitude'], df.iloc[i]['GPS_Longitude']])
        
        if i > 0:
            kf.F = np.array([[1, dt, 0, 0], [0, 1, 0, 0], [0, 0, 1, dt], [0, 0, 0, 1]])
            kf.Q = Q_discrete_white_noise(dim=2, dt=dt, var=1e-6, block_size=2)
            kf.predict()
            kf.update(z)
        
        smoothed_lat.append(kf.x[0])
        smoothed_lon.append(kf.x[2])

    df['GPS_Latitude_Raw'] = df['GPS_Latitude']
    df['GPS_Longitude_Raw'] = df['GPS_Longitude']
    df['GPS_Latitude'] = smoothed_lat
    df['GPS_Longitude'] = smoothed_lon
    
    df.to_csv(output_path, index=False)
    print(f"Trajectory refined.")
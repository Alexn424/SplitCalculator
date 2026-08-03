import pandas as pd
import numpy as np

validation_data = pd.read_csv('confidence_data/train_data.csv')

def confidence_score_regression_model(validation_data):
    X = validation_data[['TS Gaps', 'D Spikes', 'B Anomalies', 'R Inconsistency', 'R Penalty', 'Lat RMSE', 'Long RMSE']]
    y = validation_data['Error (s)']
    X_array = np.array(X)
    y_array = np.array(y)
    bias = np.ones((X_array.shape[0], 1))
    X_with_bias = np.hstack([X_array, bias])
    weights, residuals, _, _ = np.linalg.lstsq(X_with_bias, y_array, rcond=None)
    prediction = X_with_bias @ weights
    lap_residuals = y_array - prediction
    ss_residuals = np.sum(lap_residuals**2)
    ss_total = np.sum((y_array - np.mean(y_array))**2)
    r_squared = 1 - (ss_residuals / ss_total )
    print(weights)
confidence_score_regression_model(validation_data)
#print(validation_data.columns.tolist())
#print(validation_data.shape)


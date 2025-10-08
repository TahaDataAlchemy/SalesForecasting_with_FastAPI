from core.logger.logger import LOG
import pandas as pd
import numpy as np
from xgboost import XGBRegressor #type:ignore
from modules.models.modelSchema import ForecastFrequency
from core.utils.utils import evaluate_xgboost_model


def create_time_features(df, date_col='ds'):
    """
    Create time-based features from datetime column for XGBoost
    """
    df = df.copy()
    
    # Ensure date_col is a proper datetime column, not index
    if date_col not in df.columns:
        raise ValueError(f"Column '{date_col}' not found in dataframe")
    
    # Extract datetime features
    dt_series = pd.to_datetime(df[date_col])
    
    df['year'] = dt_series.dt.year
    df['month'] = dt_series.dt.month
    df['day'] = dt_series.dt.day
    df['dayofweek'] = dt_series.dt.dayofweek
    df['quarter'] = dt_series.dt.quarter
    df['dayofyear'] = dt_series.dt.dayofyear
    df['weekofyear'] = dt_series.dt.isocalendar().week.astype(int)
    
    return df

def create_lag_features(df,target_col = "y",lags = [1,2,3,7,14,30]):
    df = df.copy()
    for lag in lags:
        df[f"lag_{lag}"] = df[target_col].shift(lag)
    return df

def create_rolling_features(df,target_col = 'y',windows = [7,14,30]):
    df = df.copy()
    for window in windows:
        df[f'rolling_mean_{window}'] = df[target_col].shift(1).rolling(window=window).mean()
        df[f'rolling_std_{window}'] = df[target_col].shift(1).rolling(window=window).std()
        df[f'rolling_min_{window}'] = df[target_col].shift(1).rolling(window=window).min()
        df[f'rolling_max_{window}'] = df[target_col].shift(1).rolling(window=window).max()
    return df


def forecast_with_xgboost(ts, period_ahead, frequency: ForecastFrequency):
    """
    Generate forecast using XGBoost model with time series features
    """
    LOG.info(f"XGBoost model selected for frequency {frequency}")
    
    # Prepare data
    xgb_df = ts.reset_index()
    xgb_df.columns = ["ds", "y"]
    
    # Determine lag and rolling window sizes based on frequency
    if frequency == ForecastFrequency.DAILY:
        lags = [1, 2, 3, 7, 14, 30]
        windows = [7, 14, 30]
        min_train_size = 60  # At least 60 days
    elif frequency == ForecastFrequency.WEEKLY:
        lags = [1, 2, 4, 8, 12]
        windows = [4, 8, 12]
        min_train_size = 20  # At least 20 weeks
    else:  # MONTHLY
        lags = [1, 2, 3, 6, 12]
        windows = [3, 6, 12]
        min_train_size = 12  # At least 12 months
    
    # Create features
    xgb_df = create_time_features(xgb_df, 'ds')
    xgb_df = create_lag_features(xgb_df, 'y', lags)
    xgb_df = create_rolling_features(xgb_df, 'y', windows)
    
    # Drop rows with NaN values (from lag/rolling features)
    xgb_df = xgb_df.dropna()
    
    if len(xgb_df) < min_train_size:
        LOG.warning(f"Not enough data after feature engineering. Need at least {min_train_size} periods.")
        # Fallback to simpler features
        xgb_df = ts.reset_index()
        xgb_df.columns = ["ds", "y"]
        xgb_df = create_time_features(xgb_df, 'ds')
    
    # Define feature columns (exclude date and target)
    feature_cols = [col for col in xgb_df.columns if col not in ['ds', 'y']]
    
    # Split features and target
    X = xgb_df[feature_cols]
    y = xgb_df['y']
    
    # Train XGBoost model
    model = XGBRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        min_child_weight=1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        objective='reg:squarederror'
    )
    
    model.fit(X, y)
    
    # In-sample predictions for evaluation
    y_pred = model.predict(X)
    evaluation = evaluate_xgboost_model(y.values, y_pred)
    
    # Generate future dates
    freq_map = {
        ForecastFrequency.DAILY: "D",
        ForecastFrequency.WEEKLY: "W",
        ForecastFrequency.MONTHLY: "MS"
    }
    
    last_date = xgb_df['ds'].max()
    future_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1) if frequency == ForecastFrequency.DAILY 
              else last_date + pd.Timedelta(weeks=1) if frequency == ForecastFrequency.WEEKLY
              else last_date + pd.DateOffset(months=1),
        periods=period_ahead,
        freq=freq_map[frequency]
    )
    
    # Create future dataframe
    future_df = pd.DataFrame({'ds': future_dates})
    future_df = create_time_features(future_df, 'ds')
    
    # For lag and rolling features, we need to iteratively predict
    forecast_values = []
    extended_data = xgb_df[['ds', 'y']].copy()
    
    for i in range(period_ahead):
        current_date = future_dates[i]
        
        # Create features for current prediction
        temp_df = pd.DataFrame({'ds': [current_date]})
        temp_df = create_time_features(temp_df, 'ds')
        
        # Add lag features based on extended data
        for lag in lags:
            if len(extended_data) >= lag:
                temp_df[f'lag_{lag}'] = extended_data.iloc[-lag]['y']
            else:
                temp_df[f'lag_{lag}'] = extended_data['y'].mean()
        
        # Add rolling features
        for window in windows:
            recent_values = extended_data['y'].tail(window).values
            if len(recent_values) >= window:
                temp_df[f'rolling_mean_{window}'] = recent_values.mean()
                temp_df[f'rolling_std_{window}'] = recent_values.std()
                temp_df[f'rolling_min_{window}'] = recent_values.min()
                temp_df[f'rolling_max_{window}'] = recent_values.max()
            else:
                temp_df[f'rolling_mean_{window}'] = extended_data['y'].mean()
                temp_df[f'rolling_std_{window}'] = extended_data['y'].std()
                temp_df[f'rolling_min_{window}'] = extended_data['y'].min()
                temp_df[f'rolling_max_{window}'] = extended_data['y'].max()
        
        # Ensure all feature columns are present
        for col in feature_cols:
            if col not in temp_df.columns:
                temp_df[col] = 0
        
        # Predict
        X_future = temp_df[feature_cols]
        pred = model.predict(X_future)[0]
        forecast_values.append(pred)
        
        # Add prediction to extended data for next iteration
        extended_data = pd.concat([
            extended_data,
            pd.DataFrame({'ds': [current_date], 'y': [pred]})
        ], ignore_index=True)
    
    # Calculate prediction intervals (simple approach using residual std)
    if evaluation and evaluation['residual_std']:
        residual_std = evaluation['residual_std']
        lower_bound = [max(0, val - 1.96 * residual_std) for val in forecast_values]
        upper_bound = [val + 1.96 * residual_std for val in forecast_values]
    else:
        lower_bound = [None] * period_ahead
        upper_bound = [None] * period_ahead
    
    # Format output based on frequency
    if frequency == ForecastFrequency.DAILY:
        date_format = "%Y-%m-%d"
        period_label = "date"
    elif frequency == ForecastFrequency.WEEKLY:
        date_format = "%Y-W%U"
        period_label = "week"
    else:
        date_format = "%b-%Y"
        period_label = "month"
    
    forecast_df = pd.DataFrame({
        period_label: future_dates.strftime(date_format),
        "forecasted_sales": [round(val, 2) for val in forecast_values],
        "lower_bound": [round(val, 2) if val is not None else None for val in lower_bound],
        "upper_bound": [round(val, 2) if val is not None else None for val in upper_bound]
    })
    
    # Feature importance
    feature_importance = dict(zip(feature_cols, model.feature_importances_))
    top_features = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5])
    
    return forecast_df, evaluation, {
        "model_type": "XGBoost",
        "interval_confidence": "95%",
        "frequency": frequency.value,
        "data_points": len(ts),
        "n_estimators": model.n_estimators,
        "max_depth": model.max_depth,
        "top_features": {k: round(float(v), 4) for k, v in top_features.items()}
    }

# def forecast_with_xgboost(ts,period_ahead,frequency:ForecastFrequency):
#     LOG.info(f"XGBoost model selected for frequency {frequency}")

#     xgb_df = ts.reset_index()
#     xgb_df.columns = ["ds","y"]

#     if frequency == ForecastFrequency.DAILY:
#         lags = [1, 2, 3, 7, 14, 30]
#         windows = [7, 14, 30]
#         min_train_size = 60  # At least 60 days
#     elif frequency == ForecastFrequency.WEEKLY:
#         lags = [1, 2, 4, 8, 12]
#         windows = [4, 8, 12]
#         min_train_size = 20  # At least 20 weeks
#     else:  # MONTHLY
#         lags = [1, 2, 3, 6, 12]
#         windows = [3, 6, 12]
#         min_train_size = 12  # At least 12 months
    
#     xgb_df = create_time_features(xgb_df, 'ds')
#     xgb_df = create_lag_features(xgb_df, 'y', lags)
#     xgb_df = create_rolling_features(xgb_df, 'y', windows)
#     xgb_df = xgb_df.dropna()

#     if len(xgb_df) < min_train_size:
#         LOG.warning(f"Not enough data after feature engineering. Need at least {min_train_size} periods.")
#         # Fallback to simpler features
#         xgb_df = ts.reset_index()
#         xgb_df.columns = ["ds","y"]
#         xgb_df = create_time_features(xgb_df,"ds")
    
#     feature_cols = [col for col in xgb_df.columns if col not in ["ds","y"]]

#     X = xgb_df[feature_cols]
#     y = xgb_df['y']
    
#     model = XGBRegressor(
#         n_estimators=100,
#         learning_rate=0.1,
#         max_depth=5,
#         min_child_weight=1,
#         subsample=0.8,
#         colsample_bytree=0.8,
#         random_state=42,
#         objective='reg:squarederror'
#     )
    
#     model.fit(X, y)
#     y_pred = model.predict(X)
#     evaluation = evaluate_xgboost_model(y.values,y_pred)

#     freq_map = {
#         ForecastFrequency.DAILY: "D",
#         ForecastFrequency.WEEKLY: "W",
#         ForecastFrequency.MONTHLY: "MS"
#     }

#     last_date = xgb_df['ds'].max()
#     future_dates = pd.date_range(
#         start=last_date + pd.Timedelta(days=1) if frequency == ForecastFrequency.DAILY 
#               else last_date + pd.Timedelta(weeks=1) if frequency == ForecastFrequency.WEEKLY
#               else last_date + pd.DateOffset(months=1),
#         periods=period_ahead,
#         freq=freq_map[frequency]
#     )
    
#     # Create future dataframe
#     future_df = pd.DataFrame({'ds': future_dates})
#     future_df = create_time_features(future_df, 'ds')
    
#     # For lag and rolling features, we need to iteratively predict
#     forecast_values = []
#     extended_data = xgb_df[['ds', 'y']].copy()
    
#     for i in range(period_ahead):
#         current_date = future_dates[i]
        
#         # Create features for current prediction
#         temp_df = pd.DataFrame({'ds': [current_date]})
#         temp_df = create_time_features(temp_df, 'ds')
        
#         # Add lag features based on extended data
#         for lag in lags:
#             if len(extended_data) >= lag:
#                 temp_df[f'lag_{lag}'] = extended_data.iloc[-lag]['y']
#             else:
#                 temp_df[f'lag_{lag}'] = extended_data['y'].mean()
        
#         # Add rolling features
#         for window in windows:
#             recent_values = extended_data['y'].tail(window).values
#             if len(recent_values) >= window:
#                 temp_df[f'rolling_mean_{window}'] = recent_values.mean()
#                 temp_df[f'rolling_std_{window}'] = recent_values.std()
#                 temp_df[f'rolling_min_{window}'] = recent_values.min()
#                 temp_df[f'rolling_max_{window}'] = recent_values.max()
#             else:
#                 temp_df[f'rolling_mean_{window}'] = extended_data['y'].mean()
#                 temp_df[f'rolling_std_{window}'] = extended_data['y'].std()
#                 temp_df[f'rolling_min_{window}'] = extended_data['y'].min()
#                 temp_df[f'rolling_max_{window}'] = extended_data['y'].max()
        
#         # Ensure all feature columns are present
#         for col in feature_cols:
#             if col not in temp_df.columns:
#                 temp_df[col] = 0
        
#         # Predict
#         X_future = temp_df[feature_cols]
#         pred = model.predict(X_future)[0]
#         forecast_values.append(pred)
        
#         # Add prediction to extended data for next iteration
#         extended_data = pd.concat([
#             extended_data,
#             pd.DataFrame({'ds': [current_date], 'y': [pred]})
#         ], ignore_index=True)
    
#     # Calculate prediction intervals (simple approach using residual std)
#     if evaluation and evaluation['residual_std']:
#         residual_std = evaluation['residual_std']
#         lower_bound = [max(0, val - 1.96 * residual_std) for val in forecast_values]
#         upper_bound = [val + 1.96 * residual_std for val in forecast_values]
#     else:
#         lower_bound = [None] * period_ahead
#         upper_bound = [None] * period_ahead
    
#     # Format output based on frequency
#     if frequency == ForecastFrequency.DAILY:
#         date_format = "%Y-%m-%d"
#         period_label = "date"
#     elif frequency == ForecastFrequency.WEEKLY:
#         date_format = "%Y-W%U"
#         period_label = "week"
#     else:
#         date_format = "%b-%Y"
#         period_label = "month"
    
#     forecast_df = pd.DataFrame({
#         period_label: future_dates.strftime(date_format),
#         "forecasted_sales": [round(val, 2) for val in forecast_values],
#         "lower_bound": [round(val, 2) if val is not None else None for val in lower_bound],
#         "upper_bound": [round(val, 2) if val is not None else None for val in upper_bound]
#     })
    
#     # Feature importance
#     feature_importance = dict(zip(feature_cols, model.feature_importances_))
#     top_features = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5])
    
#     return forecast_df, evaluation, {
#         "model_type": "XGBoost",
#         "interval_confidence": "95%",
#         "frequency": frequency.value,
#         "data_points": len(ts),
#         "n_estimators": model.n_estimators,
#         "max_depth": model.max_depth,
#         "top_features": {k: round(float(v), 4) for k, v in top_features.items()}
#     }


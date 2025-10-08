import math
import numpy as np
from sklearn.metrics import mean_absolute_error,mean_squared_error,mean_absolute_percentage_error
from core.logger.logger import LOG
def clean_floats(obj):
    """Remove NaN and Inf values from nested structures"""
    if isinstance(obj, dict):
        return {k: clean_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_floats(i) for i in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj

def evaluate_arima_model(model_fit, ts):
    """Evaluate ARIMA model fitness and residuals"""
    try:
        residuals = model_fit.resid
        fitted_values = model_fit.fittedvalues
        actual = ts[len(ts) - len(fitted_values):]
        
        mae = mean_absolute_error(actual, fitted_values)
        rmse = np.sqrt(mean_squared_error(actual, fitted_values))
        
        non_zero_mask = actual != 0
        if non_zero_mask.sum() > 0:
            mape = mean_absolute_percentage_error(actual[non_zero_mask], fitted_values[non_zero_mask]) * 100
        else:
            mape = None
        
        residual_mean = float(residuals.mean())
        residual_std = float(residuals.std())
        
        ljung_box_pval = None
        if hasattr(model_fit, 'test_serial_correlation'):
            try:
                lb_test = model_fit.test_serial_correlation(method='ljungbox', lags=min(10, len(residuals)//5))
                ljung_box_pval = float(lb_test.iloc[0, 1])
            except:
                pass
        
        result = {
            "in_sample_mae": round(float(mae), 2),
            "in_sample_rmse": round(float(rmse), 2),
            "in_sample_mape": round(float(mape), 2) if mape else None,
            "aic": round(float(model_fit.aic), 2),
            "bic": round(float(model_fit.bic), 2),
            "residual_mean": round(residual_mean, 4),
            "residual_std": round(residual_std, 2),
            "data_points": len(ts)
        }
        
        if ljung_box_pval:
            result["ljung_box_pval"] = round(ljung_box_pval, 4)
        
        return result
    except Exception as e:
        LOG.warning(f"Could not evaluate ARIMA model: {e}")
        return None

def evaluate_prophet_model(model, forecast, prophet_df, ts):
    """Evaluate Prophet model with pseudo-metrics"""
    try:
        fitted_values = forecast.loc[:len(prophet_df)-1, "yhat"].values
        residuals = prophet_df["y"] - fitted_values
        actual = ts.values
        
        mae = mean_absolute_error(actual, fitted_values)
        rmse = np.sqrt(mean_squared_error(actual, fitted_values))
        
        non_zero_mask = actual != 0
        if non_zero_mask.sum() > 0:
            mape = mean_absolute_percentage_error(actual[non_zero_mask], fitted_values[non_zero_mask]) * 100
        else:
            mape = None
        
        residual_mean = float(residuals.mean())
        residual_std = float(residuals.std())
        
        result = {
            "in_sample_mae": round(float(mae), 2),
            "in_sample_rmse": round(float(rmse), 2),
            "in_sample_mape": round(float(mape), 2) if mape else None,
            "aic": None,  # Prophet doesn't provide AIC/BIC
            "bic": None,
            "residual_mean": round(residual_mean, 4),
            "residual_std": round(residual_std, 2),
            "data_points": len(ts)
        }
        
        return result
    except Exception as e:
        LOG.warning(f"Could not evaluate Prophet model: {e}")
        return None

def evaluate_xgboost_model(y_true, y_pred):
    """
    Evaluate XGBoost model performance
    """
    try:
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        
        non_zero_mask = y_true != 0
        if non_zero_mask.sum() > 0:
            mape = mean_absolute_percentage_error(y_true[non_zero_mask], y_pred[non_zero_mask]) * 100
        else:
            mape = None
        
        residuals = y_true - y_pred
        residual_mean = float(residuals.mean())
        residual_std = float(residuals.std())
        
        # R-squared
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - y_true.mean()) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        result = {
            "in_sample_mae": round(float(mae), 2),
            "in_sample_rmse": round(float(rmse), 2),
            "in_sample_mape": round(float(mape), 2) if mape else None,
            "r_squared": round(float(r2), 4),
            "residual_mean": round(residual_mean, 4),
            "residual_std": round(residual_std, 2),
            "data_points": len(y_true)
        }
        
        return result
    except Exception as e:
        LOG.warning(f"Could not evaluate XGBoost model: {e}")
        return None
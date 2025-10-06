from modules.ORM.run_query import run_query
from core.logger.logger import LOG
import pandas as pd
from modules.data.sql_queries.analytical_queries.monthlySales import SalesQuery
from fastapi import APIRouter, HTTPException, Query
from modules.ORM.orm import engine
from sqlalchemy.orm import Session
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
import numpy as np
from prophet import Prophet
import math

session = Session(bind=engine)
def clean_floats(obj):
    if isinstance(obj, dict):
        return {k: clean_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_floats(i) for i in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj


router = APIRouter(
    prefix="/api/v1/data_forecast/Prophet", tags=["forecast"]
)

def evaluate_model(model_fit, ts):
    """
    Evaluate ARIMA model fitness and residuals.
    Returns in-sample fit metrics and diagnostic information.
    """
    try:
        # Get residuals
        residuals = model_fit.resid
        
        # In-sample predictions
        fitted_values = model_fit.fittedvalues
        
        # Calculate in-sample metrics (where fitted values exist)
        actual = ts[len(ts) - len(fitted_values):]
        mae = mean_absolute_error(actual, fitted_values)
        rmse = np.sqrt(mean_squared_error(actual, fitted_values))
        
        # Avoid MAPE if there are zero values
        non_zero_mask = actual != 0
        if non_zero_mask.sum() > 0:
            mape = mean_absolute_percentage_error(actual[non_zero_mask], fitted_values[non_zero_mask]) * 100
        else:
            mape = None
        
        # Residual statistics
        residual_mean = float(residuals.mean())
        residual_std = float(residuals.std())
        
        # Ljung-Box test p-value (tests if residuals are white noise)
        ljung_box_pval = None
        if hasattr(model_fit, 'test_serial_correlation'):
            try:
                lb_test = model_fit.test_serial_correlation(method='ljungbox', lags=min(10, len(residuals)//5))
                ljung_box_pval = float(lb_test.iloc[0, 1])  # p-value of first lag
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
        LOG.warning(f"Could not evaluate model: {e}")
        return None
    

@router.get("/monthly_sales/product_sales_forecast")
async def get_product_sales_forecast(
    product_name: str = Query(..., description="Product name to forecast"),
    months_ahead: int = Query(3, description="Number of months to forecast (default=3)")
):
    """
    Forecast monthly sales for a given product using Prophet model.
    """
    try:
        # Fetch sales data
        df = run_query(SalesQuery.product_wise_monthly_sales(session).statement)
        if df.empty:
            raise HTTPException(status_code=404, detail="No sales data found")

        # Normalize product name
        df["product_name"] = df["product_name"].str.strip()

        # Filter for the requested product
        df = df[df["product_name"].str.lower() == product_name.strip().lower()]
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No sales data found for '{product_name}'")

        # Convert and clean date column
        df["month"] = pd.to_datetime(df["month"], utc=True).dt.tz_convert(None)

        # Aggregate by month
        ts = df.groupby("month")["total_sales"].sum().sort_index()

        if len(ts) < 3:
            raise HTTPException(status_code=400, detail="Not enough historical data for forecasting")

        # Prepare data for Prophet
        prophet_df = ts.reset_index()
        prophet_df.columns = ["ds", "y"]

        # Initialize and fit Prophet model
        model = Prophet(
            interval_width=0.95,
            daily_seasonality=False,
            weekly_seasonality=False,
            yearly_seasonality=True
        )
        model.fit(prophet_df)

        # Create future dataframe for forecasting
        future = model.make_future_dataframe(periods=months_ahead, freq="MS")
        forecast = model.predict(future)

        # Extract forecasted values for future months only
        future_forecast = forecast[forecast["ds"] > prophet_df["ds"].max()][["ds", "yhat", "yhat_lower", "yhat_upper"]]

        # Evaluation metrics on historical (in-sample) data
        evaluation = evaluate_model(model_fit=type('fit', (), {
            "resid": prophet_df["y"] - forecast.loc[:len(prophet_df)-1, "yhat"].values,
            "fittedvalues": forecast.loc[:len(prophet_df)-1, "yhat"].values,
            "aic": np.nan,  # Prophet does not provide AIC/BIC
            "bic": np.nan
        })(), ts=ts)

        # Format forecast results
        forecast_df = pd.DataFrame({
            "month": future_forecast["ds"].dt.strftime("%b-%Y"),
            "forecasted_sales": future_forecast["yhat"].round(2),
            "lower_bound": future_forecast["yhat_lower"].round(2),
            "upper_bound": future_forecast["yhat_upper"].round(2),
        })

        # Prepare history
        history_df = prophet_df.assign(
            month=prophet_df["ds"].dt.strftime("%b-%Y")
        )[["month", "y"]].rename(columns={"y": "actual_sales"})

        # Prepare response
        return clean_floats({
            "product": product_name,
            "last_known_month": prophet_df["ds"].max().strftime("%b-%Y"),
            "history": history_df.to_dict(orient="records"),
            "forecast": forecast_df.to_dict(orient="records"),
            "evaluation_metrics": evaluation,
            "model_info": {
                "model_type": "Prophet",
                "interval_confidence": "95%",
                "data_points": len(ts)
            }
        })

    except Exception as e:
        LOG.error(f"Error generating Prophet forecast: {e}", extra={"module": "Prophet"})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/monthly_sales/customer_wise")
async def get_customer_sales_forecast(
    customer_name: str = Query(..., description="Customer name to filter"),
    product_name: str | None = Query(default=None, description="Filter by product name"),
    months_ahead: int = Query(3, description="Number of months to forecast (default=3)")
):
    """
    Forecast monthly sales for a given customer (and optionally product)
    using ARIMA time series forecasting.
    """
    try:
        # Run query depending on whether product_name is supplied
        if product_name:
            df = run_query(SalesQuery.customer_product_wise_sales(session).statement)
        else:
            df = run_query(SalesQuery.customer_wise_sales(session).statement)

        if df.empty:
            raise HTTPException(status_code=404, detail="No sales data found")

        # Normalize customer and product names
        df["company_name"] = df["company_name"].astype(str).str.strip().str.lower()
        if "product_name" in df.columns:
            df["product_name"] = df["product_name"].astype(str).str.strip().str.lower()

        # Normalize inputs
        cust = customer_name.strip().lower()
        prod = product_name.strip().lower() if product_name else None

        # Filter for customer
        df = df[df["company_name"] == cust]
        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No sales data found for customer '{customer_name}'"
            )

        # Filter for product if provided
        if prod:
            df = df[df["product_name"] == prod]
            if df.empty:
                raise HTTPException(
                    status_code=404,
                    detail=f"No sales data found for product '{product_name}' and customer '{customer_name}'"
                )

        # Convert month column → datetime (tz-naive)
        df["month"] = pd.to_datetime(df["month"], utc=True).dt.tz_localize(None)

        # Aggregate by month
        ts = df.groupby("month")["total_sales"].sum().sort_index()

        if len(ts) < 3:
            raise HTTPException(
                status_code=400,
                detail="Not enough historical data for forecasting"
            )

        # Fit ARIMA model
        prophet_df = ts.reset_index()
        prophet_df.columns = ["ds", "y"]

        # Initialize and fit Prophet model
        model = Prophet(
            interval_width=0.95,
            daily_seasonality=False,
            weekly_seasonality=False,
            yearly_seasonality=True
        )
        model.fit(prophet_df)

        # Create future dataframe for forecasting
        future = model.make_future_dataframe(periods=months_ahead, freq="MS")
        forecast = model.predict(future)

        # Extract forecasted values for future months only
        future_forecast = forecast[forecast["ds"] > prophet_df["ds"].max()][["ds", "yhat", "yhat_lower", "yhat_upper"]]

        # Evaluation metrics on historical (in-sample) data
        evaluation = evaluate_model(model_fit=type('fit', (), {
            "resid": prophet_df["y"] - forecast.loc[:len(prophet_df)-1, "yhat"].values,
            "fittedvalues": forecast.loc[:len(prophet_df)-1, "yhat"].values,
            "aic": np.nan,  # Prophet does not provide AIC/BIC
            "bic": np.nan
        })(), ts=ts)

        # Format forecast results
        forecast_df = pd.DataFrame({
            "month": future_forecast["ds"].dt.strftime("%b-%Y"),
            "forecasted_sales": future_forecast["yhat"].round(2),
            "lower_bound": future_forecast["yhat_lower"].round(2),
            "upper_bound": future_forecast["yhat_upper"].round(2),
        })

        # Prepare history
        history_df = prophet_df.assign(
            month=prophet_df["ds"].dt.strftime("%b-%Y")
        )[["month", "y"]].rename(columns={"y": "actual_sales"})

        # Prepare response
        return clean_floats({
            "customer_name":customer_name,
            "product": product_name,
            "last_known_month": prophet_df["ds"].max().strftime("%b-%Y"),
            "history": history_df.to_dict(orient="records"),
            "forecast": forecast_df.to_dict(orient="records"),
            "evaluation_metrics": evaluation,
            "model_info": {
                "model_type": "Prophet",
                "interval_confidence": "95%",
                "data_points": len(ts)
            }
        })

    except Exception as e:
        LOG.error(f"Error generating Prophet forecast: {e}", extra={"module": "Prophet"})
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/monthly_sales/city_wise")
async def get_city_sales_forecast(
    city_name: str = Query(..., description="City name to filter"),
    months_ahead: int = Query(3, description="Number of months to forecast (default=3)")
):
    """
    Forecast monthly sales for a given city using ARIMA.
    """
    try:
        # Fetch sales data
        df = run_query(SalesQuery.city_wise_sales(session).statement)
        if df.empty:
            raise HTTPException(status_code=404, detail="No sales data found")

        # Normalize city name
        df["city"] = df["city"].astype(str).str.strip().str.lower()
        city = city_name.strip().lower()

        # Filter for the requested city
        df = df[df["city"] == city]
        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No sales data found for city '{city_name}'"
            )

        # Convert month column → datetime
        df["month"] = pd.to_datetime(df["month"], utc=True).dt.tz_localize(None)

        # Aggregate sales by month
        ts = df.groupby("month")["total_sales"].sum().sort_index()

        if len(ts) < 3:
            raise HTTPException(
                status_code=400,
                detail="Not enough historical data for forecasting"
            )

        # Fit ARIMA model
        prophet_df = ts.reset_index()
        prophet_df.columns = ["ds", "y"]

        # Initialize and fit Prophet model
        model = Prophet(
            interval_width=0.95,
            daily_seasonality=False,
            weekly_seasonality=False,
            yearly_seasonality=True
        )
        model.fit(prophet_df)

        # Create future dataframe for forecasting
        future = model.make_future_dataframe(periods=months_ahead, freq="MS")
        forecast = model.predict(future)

        # Extract forecasted values for future months only
        future_forecast = forecast[forecast["ds"] > prophet_df["ds"].max()][["ds", "yhat", "yhat_lower", "yhat_upper"]]

        # Evaluation metrics on historical (in-sample) data
        evaluation = evaluate_model(model_fit=type('fit', (), {
            "resid": prophet_df["y"] - forecast.loc[:len(prophet_df)-1, "yhat"].values,
            "fittedvalues": forecast.loc[:len(prophet_df)-1, "yhat"].values,
            "aic": np.nan,  # Prophet does not provide AIC/BIC
            "bic": np.nan
        })(), ts=ts)

        # Format forecast results
        forecast_df = pd.DataFrame({
            "month": future_forecast["ds"].dt.strftime("%b-%Y"),
            "forecasted_sales": future_forecast["yhat"].round(2),
            "lower_bound": future_forecast["yhat_lower"].round(2),
            "upper_bound": future_forecast["yhat_upper"].round(2),
        })

        # Prepare history
        history_df = prophet_df.assign(
            month=prophet_df["ds"].dt.strftime("%b-%Y")
        )[["month", "y"]].rename(columns={"y": "actual_sales"})

        # Prepare response
        return clean_floats({
            "city":city_name,
            "last_known_month": prophet_df["ds"].max().strftime("%b-%Y"),
            "history": history_df.to_dict(orient="records"),
            "forecast": forecast_df.to_dict(orient="records"),
            "evaluation_metrics": evaluation,
            "model_info": {
                "model_type": "Prophet",
                "interval_confidence": "95%",
                "data_points": len(ts)
            }
        })

    except Exception as e:
        LOG.error(f"Error generating Prophet forecast: {e}", extra={"module": "Prophet"})
        raise HTTPException(status_code=500, detail="Internal server error")
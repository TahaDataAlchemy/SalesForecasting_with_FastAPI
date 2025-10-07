from modules.ORM.run_query import run_query
from core.logger.logger import LOG
import pandas as pd
from modules.data.sql_queries.analytical_queries.monthlySales import SalesQuery
from fastapi import APIRouter, HTTPException, Query
from modules.ORM.orm import engine
from sqlalchemy.orm import Session
from modules.models.modelSchema import ModelType,ForecastFrequency
from core.utils.utils import clean_floats
from modules.models.Prophet import forecast_with_prophet
from modules.models.Arima import forecast_with_arima


session = Session(bind=engine)

router = APIRouter(
    prefix = "/api/v1/data_forecast",
    tags = ["forecast"]
)

def generate_forecast(ts, periods_ahead, model_type: ModelType, frequency: ForecastFrequency):
    """Generate forecast based on selected model"""
    if model_type == ModelType.ARIMA:
        return forecast_with_arima(ts, periods_ahead, frequency)
    elif model_type == ModelType.PROPHET:
        return forecast_with_prophet(ts, periods_ahead, frequency)
    else:
        raise ValueError(f"Unknown model type: {model_type}")

@router.get("/sales/product_sales_forecast")
async def gete_product_sales_forecast(
    product_name:str = Query(..., description = "Product name to forecast"),
    periods_ahead: int = Query(3,description = "Number of periods to forecast default = 3"),
    model :ModelType = Query(ModelType.ARIMA,description = "Forecasting model to use (arima or prophet)"),
    frequency: ForecastFrequency = Query(ForecastFrequency.MONTHLY, description="Forecast frequency (daily, weekly, monthly)")
):
    try:
        LOG.info(f"frequency selected {frequency}")
        df = run_query(SalesQuery.product_wise_sales(session,frequency).statement)
        if df.empty:
            raise HTTPException(status_code=404,detail = "No Sales data found")
        
        df["product_name"] = df["product_name"].str.strip()
        df = df[df["product_name"].str.lower() == product_name.strip().lower()]
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No sales data found for '{product_name}'")
        
        df["period"] = pd.to_datetime(df["period"],utc = True).dt.tz_convert(None)

        ts = df.groupby("period")["total_sales"].sum().sort_index()

        if len(ts)<3:
            raise HTTPException(status_code = 400,detail = "Not enough historical data for forecasting")
        
        forecast_df,evaluation,model_info = generate_forecast(ts,periods_ahead,model,frequency)

        if frequency == ForecastFrequency.DAILY:
            period_label, date_format = "date", "%Y-%m-%d"
        elif frequency == ForecastFrequency.WEEKLY:
            period_label, date_format = "week", "%Y-W%U"
        else:  # MONTHLY
            period_label, date_format = "month", "%b-%Y"
        
        history_df = ts.reset_index().assign(**{period_label: ts.index.strftime(date_format)})
        history_df = history_df[[period_label, "total_sales"]].rename(columns={"total_sales": "actual_sales"})
        
        # Build response
        response = {
            "product": product_name,
            f"last_known_{period_label}": ts.index[-1].strftime(date_format),
            "history": history_df.to_dict(orient="records"),
            "forecast": forecast_df.to_dict(orient="records"),
            "evaluation_metrics": evaluation,
            "model_info": model_info
        }
        
        # Prophet may return floats with NaN/inf, so we clean them
        return clean_floats(response) if model == ModelType.PROPHET else response
    
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error generating forecast: {e}", extra={"module": model.value})
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/sales/customer_sales_forecast")
async def get_customer_sales_forecast(
    customer_name: str = Query(..., description="Customer name to filter"),
    product_name: str | None = Query(default=None, description="Optional product name to filter"),
    periods_ahead: int = Query(3, description="Number of periods to forecast (default=3)"),
    model: ModelType = Query(ModelType.ARIMA, description="Forecasting model to use (arima or prophet)"),
    frequency: ForecastFrequency = Query(ForecastFrequency.MONTHLY, description="Forecast frequency (daily, weekly, monthly)")
):
    try:
        LOG.info(f"Forecast request - customer: {customer_name}, product: {product_name}, freq: {frequency}")

        if product_name:
            df = run_query(SalesQuery.customer_product_wise_sales(session, frequency).statement)
        else:
            df = run_query(SalesQuery.customer_wise_sales(session, frequency).statement)

        if df.empty:
            raise HTTPException(status_code=404, detail="No sales data found")

        df["company_name"] = df["company_name"].astype(str).str.strip().str.lower()
        if "product_name" in df.columns:
            df["product_name"] = df["product_name"].astype(str).str.strip().str.lower()

        customer_name_clean = customer_name.strip().lower()
        product_name_clean = product_name.strip().lower() if product_name else None

        df = df[df["company_name"] == customer_name_clean]
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No sales data found for customer '{customer_name}'")

        if product_name_clean and "product_name" in df.columns:
            df = df[df["product_name"] == product_name_clean]
            if df.empty:
                raise HTTPException(
                    status_code=404,
                    detail=f"No sales data found for product '{product_name}' and customer '{customer_name}'"
                )

        df["period"] = pd.to_datetime(df["period"], utc=True).dt.tz_convert(None)

        ts = df.groupby("period")["total_sales"].sum().sort_index()

        if len(ts) < 3:
            raise HTTPException(status_code=400, detail="Not enough historical data for forecasting")

        forecast_df, evaluation, model_info = generate_forecast(ts, periods_ahead, model, frequency)

        if frequency == ForecastFrequency.DAILY:
            period_label, date_format = "date", "%Y-%m-%d"
        elif frequency == ForecastFrequency.WEEKLY:
            period_label, date_format = "week", "%Y-W%U"
        else:
            period_label, date_format = "month", "%b-%Y"

        history_df = ts.reset_index().assign(**{period_label: ts.index.strftime(date_format)})
        history_df = history_df[[period_label, "total_sales"]].rename(columns={"total_sales": "actual_sales"})

        response = {
            "customer": customer_name,
            "product": product_name if product_name else "All Products",
            f"last_known_{period_label}": ts.index[-1].strftime(date_format),
            "history": history_df.to_dict(orient="records"),
            "forecast": forecast_df.to_dict(orient="records"),
            "evaluation_metrics": evaluation,
            "model_info": model_info
        }

        # Prophet often has float precision/NaN issues, so clean
        return clean_floats(response) if model == ModelType.PROPHET else response

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error generating forecast: {e}", extra={"module": model.value})
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/sales/city_wise_forecast")
async def get_city_sales_forecast(
    city_name: str = Query(..., description="City name to filter"),
    periods_ahead: int = Query(3, description="Number of periods to forecast (default=3)"),
    model: ModelType = Query(ModelType.ARIMA, description="Forecasting model to use (arima or prophet)"),
    frequency: ForecastFrequency = Query(ForecastFrequency.MONTHLY, description="Forecast frequency (daily, weekly, monthly)")
):
    try:
        LOG.info(f"Running city-wise forecast for {city_name} using {model.value} ({frequency.value})")

        df = run_query(SalesQuery.city_wise_sales(session, frequency).statement)
        if df.empty:
            raise HTTPException(status_code=404, detail="No sales data found")

        df["city"] = df["city"].astype(str).str.strip().str.lower()
        city = city_name.strip().lower()

        df = df[df["city"] == city]
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No sales data found for city '{city_name}'")

        df["period"] = pd.to_datetime(df["period"], utc=True).dt.tz_localize(None)

        ts = df.groupby("period")["total_sales"].sum().sort_index()
        if len(ts) < 3:
            raise HTTPException(status_code=400, detail="Not enough historical data for forecasting")

        forecast_df, evaluation, model_info = generate_forecast(ts, periods_ahead, model, frequency)

        if frequency == ForecastFrequency.DAILY:
            period_label, date_format = "date", "%Y-%m-%d"
        elif frequency == ForecastFrequency.WEEKLY:
            period_label, date_format = "week", "%Y-W%U"
        else:  # MONTHLY
            period_label, date_format = "month", "%b-%Y"

        history_df = ts.reset_index().assign(**{period_label: ts.index.strftime(date_format)})
        history_df = history_df[[period_label, "total_sales"]].rename(columns={"total_sales": "actual_sales"})

        response = {
            "city": city_name,
            f"last_known_{period_label}": ts.index[-1].strftime(date_format),
            "history": history_df.to_dict(orient="records"),
            "forecast": forecast_df.to_dict(orient="records"),
            "evaluation_metrics": evaluation,
            "model_info": model_info
        }

        return clean_floats(response) if model == ModelType.PROPHET else response

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error generating city forecast: {e}", extra={"module": model.value})
        raise HTTPException(status_code=500, detail="Internal server error")
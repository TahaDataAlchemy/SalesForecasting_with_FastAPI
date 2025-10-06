from modules.ORM.run_query import run_query
from core.logger.logger import LOG
import pandas as pd
from modules.data.sql_queries.analytical_queries.monthlySales import SalesQuery
from fastapi import APIRouter, HTTPException, Query
from statsmodels.tsa.arima.model import ARIMA
from modules.ORM.orm import engine
from sqlalchemy.orm import Session

session = Session(bind=engine)

router = APIRouter(
    prefix="/api/v1/data_forecast/Arima", tags=["forecast"]
)

@router.get("/monthly_sales/product_sales_forecast")
async def get_product_sales_forecast(
    product_name: str = Query(..., description="Product name to forecast"),
    months_ahead: int = Query(3, description="Number of months to forecast (default=3)")
):
    """
    Forecast sales for a given product using ARIMA model.
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

        df["month"] = pd.to_datetime(df["month"], utc=True).dt.tz_convert(None)

        # Aggregate by month
        ts = df.groupby("month")["total_sales"].sum().sort_index()

        if len(ts) < 3:
            raise HTTPException(status_code=400, detail="Not enough historical data for forecasting")

        # Fit ARIMA model
        model = ARIMA(ts, order=(1, 1, 1))
        model_fit = model.fit()

        # Forecast future months
        forecast = model_fit.forecast(steps=months_ahead)

        # Generate future month labels
        forecast_index = pd.date_range(
            start=ts.index[-1] + pd.offsets.MonthBegin(1),
            periods=months_ahead,
            freq="MS"
        )

        forecast_df = pd.DataFrame({
            "month": forecast_index.strftime("%b-%Y"),
            "forecasted_sales": forecast.values
        })

        # Prepare response
        return {
            "product": product_name,
            "last_known_month": ts.index[-1].strftime("%b-%Y"),
            "history": ts.reset_index()
                        .assign(month=ts.index.strftime("%b-%Y"))
                        .to_dict(orient="records"),
            "forecast": forecast_df.to_dict(orient="records")
        }

    except Exception as e:
        LOG.error(f"Error generating forecast: {e}", extra={"module": "Arima"})
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
        model = ARIMA(ts, order=(1, 1, 1))
        model_fit = model.fit()

        # Forecast future months
        forecast = model_fit.forecast(steps=months_ahead)

        # Generate forecast index
        forecast_index = pd.date_range(
            start=ts.index[-1] + pd.offsets.MonthBegin(1),
            periods=months_ahead,
            freq="MS"
        )

        forecast_df = pd.DataFrame({
            "month": forecast_index.strftime("%b-%Y"),
            "forecasted_sales": forecast.values
        })

        # Response payload
        return {
            "customer": customer_name,
            "product": product_name if product_name else "All Products",
            "last_known_month": ts.index[-1].strftime("%b-%Y"),
            "history": ts.reset_index()
                        .assign(month=ts.index.strftime("%b-%Y"))
                        .to_dict(orient="records"),
            "forecast": forecast_df.to_dict(orient="records")
        }

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error generating forecast: {e}", extra={"model_module": "Arima"})
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
        model = ARIMA(ts, order=(1, 1, 1))
        model_fit = model.fit()

        # Forecast
        forecast = model_fit.forecast(steps=months_ahead)

        # Future month labels
        forecast_index = pd.date_range(
            start=ts.index[-1] + pd.offsets.MonthBegin(1),
            periods=months_ahead,
            freq="MS"
        )

        forecast_df = pd.DataFrame({
            "month": forecast_index.strftime("%b-%Y"),
            "forecasted_sales": forecast.values
        })

        return {
            "city": city_name,
            "last_known_month": ts.index[-1].strftime("%b-%Y"),
            "history": ts.reset_index()
                        .assign(month=ts.index.strftime("%b-%Y"))
                        .to_dict(orient="records"),
            "forecast": forecast_df.to_dict(orient="records")
        }

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error generating city forecast: {e}", extra={"model_module": "Arima"})
        raise HTTPException(status_code=500, detail="Internal server error")

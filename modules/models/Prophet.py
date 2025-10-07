from core.logger.logger import LOG
import pandas as pd
from prophet import Prophet
from modules.models.modelSchema import ForecastFrequency
from modules.models.modelSchema import ForecastFrequency
from core.utils.utils import evaluate_prophet_model

def forecast_with_prophet(ts,period_ahead,frequency:ForecastFrequency):
    LOG.info(f"Prophet model Selected for frequency {frequency}")
    prophet_df = ts.reset_index()
    prophet_df.columns = ["ds","y"]

    model = Prophet(
        interval_width=0.95,
        daily_seasonality=(frequency == ForecastFrequency.DAILY),
        weekly_seasonality= (frequency == ForecastFrequency.WEEKLY),
        yearly_seasonality=True
    )
    model.fit(prophet_df)

    freq_map = {
        ForecastFrequency.DAILY:"D",
        ForecastFrequency.WEEKLY:"W",
        ForecastFrequency.MONTHLY:"MS"
    }

    freq_str = freq_map[frequency]

    future = model.make_future_dataframe(periods=period_ahead,freq=freq_str)
    forecast = model.predict(future)

    future_forecast = forecast[forecast["ds"] > prophet_df["ds"].max()][["ds", "yhat", "yhat_lower", "yhat_upper"]]

    evaluation = evaluate_prophet_model(model,forecast,prophet_df,ts)

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
        period_label: future_forecast["ds"].dt.strftime(date_format),
        "forecasted_sales": future_forecast["yhat"].round(2),
        "lower_bound": future_forecast["yhat_lower"].round(2),
        "upper_bound": future_forecast["yhat_upper"].round(2)
    })
        
    return forecast_df, evaluation, {
        "model_type": "Prophet",
        "interval_confidence": "95%",
        "frequency": frequency.value,
        "data_points": len(ts)
    }
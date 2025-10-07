from core.logger.logger import LOG
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from modules.models.modelSchema import ForecastFrequency
from core.utils.utils import evaluate_arima_model

def forecast_with_arima(ts,periods_ahead,frequency:ForecastFrequency):
    LOG.info(f"Arima Model Selected for the frequency {frequency}")
    model = ARIMA(ts,order=(1,1,1))
    model_fit = model.fit()

    evaluation = evaluate_arima_model(model_fit,ts)
    forecast = model_fit.forecast(steps = periods_ahead)

    freq_map = {
        ForecastFrequency.DAILY:("D",pd.offsets.Day(1)),
        ForecastFrequency.WEEKLY:("W",pd.offsets.Week(1)),
        ForecastFrequency.MONTHLY:("MS",pd.offsets.MonthBegin(1))
    }
    freq_str,offset = freq_map[frequency]

    forecast_index = pd.date_range(
        start=ts.index[-1]+offset,
        periods=periods_ahead,
        freq=freq_str
    )

    if frequency == ForecastFrequency.DAILY:
        date_format = "%Y-%m-%d"
        period_label = "date"
    
    elif frequency == ForecastFrequency.WEEKLY:
        date_format = "%Y-W%U"
        period_label ="week"

    else:
        date_format = "%b-%Y"
        period_label = "month"
    
    forecast_df = pd.DataFrame({
        period_label:forecast_index.strftime(date_format),
        "forecasted_sales":forecast.values,
        "lower_bound":None,
        "upper_bound":None
    })

    return forecast_df,evaluation,{
        "model_type": "ARIMA",
        "model_order": (1, 1, 1),
        "interval_confidence": None,
        "frequency": frequency.value,
        "data_points": len(ts)
    }


from enum import Enum

class ModelType(str,Enum):
    ARIMA = "arima"
    PROPHET = "prophet"

class ForecastFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
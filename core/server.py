from fastapi import FastAPI
from fastapi.middleware import Middleware
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from core.middlewares.middleware import middleware_handler




from config import CONFIG
from modules.healthcheck.healthcheck_routes import API_ROUTER
from modules.logviewer.log_viewer_routes import API_ROUTER as LOG_VIEWER_ROUTER
from modules.ORM import orm
from modules.data.data_prep import router as data_router
from modules.data.SummaryStats import router as data_analysis_router
from modules.models.Arima import router as forecast_router
# from modules.data import dataAnalysis


# df = dataAnalysis.analyze_data("SELECT * FROM products;")

def init_routers(app_: FastAPI) -> None:
    app_.include_router(API_ROUTER)
    app_.include_router(data_router)
    app_.include_router(data_analysis_router)
    app_.include_router(forecast_router)
    app_.include_router(LOG_VIEWER_ROUTER)


def make_middleware() -> list[Middleware]:
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ]
    return middleware


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Code to run *before* the application starts (e.g., initialize DB, start background tasks)
#     yield
#     # Code to run *after* the application shuts down (e.g., cleanup, close connections)


def create_app() -> FastAPI:
    app_ = FastAPI(
        title=CONFIG.app_name,
        description=CONFIG.description,
        version=CONFIG.version,
        middleware=make_middleware(),
        # lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        
    )
    init_routers(app_=app_)
    middleware_handler(app=app_)
    return app_


app = create_app()
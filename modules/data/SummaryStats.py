from fastapi import APIRouter, HTTPException, Query
from modules.ORM.run_query import run_query
from core.logger.logger import LOG
import pandas as pd

router = APIRouter(
    prefix="/api/v1/data_analysis", tags=["data-analysis"]
)

@router.get("/table_stats")
async def get_table_stats(
    table_name: str = Query(..., description="Name of the table to analyze")
):
    """
    Analyze a table by fetching its data and returning summary statistics.
    """
    LOG.info(f"Starting analysis for table: {table_name}")
    try:
        # Query entire table
        query = f"SELECT * FROM {table_name};"
        df = run_query(query)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found in table '{table_name}'")

        LOG.info(f"Data retrieved: {df.shape[0]} rows and {df.shape[1]} columns.")

        # Summary statistics
        summary = df.describe(include="all").fillna("").to_dict()

        # Missing values
        missing_values = df.isnull().sum().to_dict()

        # Return first 10 rows for inspection
        sample_data = df.head(10).to_dict(orient="records")

        return {
            "table": table_name,
            "rows": df.shape[0],
            "columns": df.shape[1],
            "sample_data": sample_data,
            "summary": summary,
            "missing_values": missing_values,
        }

    except Exception as e:
        LOG.error(f"Error analyzing table {table_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

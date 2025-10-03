# from modules.ORM.run_query import run_query
# from core.logger.logger import LOG
# import pandas as pd
# from modules.data.sql_queries.analytical_queries.monthlySales import SalesQuery
# from fastapi import APIRouter, HTTPException, Query

# router = APIRouter(
#     prefix="/api/v1/data_agg", tags=["data"]
# )

# @router.get("/monthly_sales/product_wise")
# async def get_product_wise_monthly_sales(
#     product_name: str | None = Query(default=None, description="Filter sales by product name")
# ):
#     try:
#         # Run SQL query
#         df = run_query(SalesQuery.PRODUCT_WISE_MONTHLY_SALES)

#         if df.empty:
#             raise HTTPException(status_code=404, detail="No sales data found")

#         # Filter by product if provided
#         if product_name:
#             df = df[df["product_name"].str.lower() == product_name.lower()]
#             if df.empty:
#                 raise HTTPException(status_code=404, detail=f"No sales data found for product '{product_name}'")

#         # Pivot → products as rows, months as columns, total_sales as values
#         pivot_df = df.pivot_table(
#             index="product_name",
#             columns="month",
#             values="total_sales",
#             aggfunc="sum",
#             fill_value=0
#         ).reset_index()

#         # Add "Total" column
#         pivot_df["Total"] = pivot_df.drop(columns=["product_name"]).sum(axis=1)

#         if not product_name:
#             total_row = pivot_df.drop(columns=["product_name"]).sum()
#             total_row["product_name"] = "All Products"
#             pivot_df = pd.concat([pivot_df, pd.DataFrame([total_row])], ignore_index=True)

#         pivot_df.rename(
#             columns={col: pd.to_datetime(col).strftime("%b-%Y") for col in pivot_df.columns if isinstance(col, pd.Timestamp)},
#             inplace=True
#         )

#         return pivot_df.to_dict(orient="records")

#     except Exception as e:
#         LOG.error(f"Error fetching monthly sales: {e}")
#         raise HTTPException(status_code=500, detail="Internal server error")

from modules.ORM.run_query import run_query
from core.logger.logger import LOG
import pandas as pd
from modules.data.sql_queries.analytical_queries.monthlySales import SalesQuery
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(
    prefix="/api/v1/data_agg", tags=["data"]
)

@router.get("/monthly_sales/product_wise")
async def get_product_wise_monthly_sales(
    product_name: str | None = Query(default=None, description="Filter sales by product name")
):
    try:
        # Run SQL query
        df = run_query(SalesQuery.PRODUCT_WISE_MONTHLY_SALES)

        if df.empty:
            raise HTTPException(status_code=404, detail="No sales data found")

        # Normalize product_name column
        df["product_name"] = df["product_name"].str.strip()

        # Filter by product if provided
        if product_name:
            # Flexible filter: case-insensitive match, trims spaces
            df = df[df["product_name"].str.lower() == product_name.strip().lower()]

            if df.empty:
                raise HTTPException(
                    status_code=404, 
                    detail=f"No sales data found for product '{product_name}'"
                )

        # Pivot → products as rows, months as columns, total_sales as values
        pivot_df = df.pivot_table(
            index="product_name",
            columns="month",
            values="total_sales",
            aggfunc="sum",
            fill_value=0
        ).reset_index()

        # Add "Total" column
        pivot_df["Total"] = pivot_df.drop(columns=["product_name"]).sum(axis=1)

        # If no specific product is requested, add an "All Products" total row
        if not product_name:
            total_row = pivot_df.drop(columns=["product_name"]).sum()
            total_row["product_name"] = "All Products"
            pivot_df = pd.concat([pivot_df, pd.DataFrame([total_row])], ignore_index=True)

        # Convert datetime columns to "MMM-YYYY"
        pivot_df.rename(
            columns={
                col: pd.to_datetime(col).strftime("%b-%Y")
                for col in pivot_df.columns
                if isinstance(col, pd.Timestamp)
            },
            inplace=True
        )

        return pivot_df.to_dict(orient="records")

    except Exception as e:
        LOG.error(f"Error fetching monthly sales: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

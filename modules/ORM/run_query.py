from modules.ORM.orm import engine
import pandas as pd
from core.logger.logger import LOG

def run_query(query: str) -> pd.DataFrame:
    """
    Executes a SQL query and returns the result as a pandas DataFrame.

    Args:
        query (str): The SQL query to be executed."""
    LOG.info(f"Executing query: {query}")
    try:
        with engine.connect() as connection:
            df = pd.read_sql_query(query,connection)
        LOG.info("Query executed successfully.")
        return df
    except Exception as e:
        LOG.error(f"Error executing query: {e}")
        raise


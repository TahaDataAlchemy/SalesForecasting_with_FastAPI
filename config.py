import tomllib
from os import getenv
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel


load_dotenv()

with open("pyproject.toml", "rb") as f:
    toml_object: dict[str] = tomllib.load(f).get("project", {})
    name = toml_object.get("name")
    description = toml_object.get("description")
    version = toml_object.get("version")

class ConfigClass(BaseModel):
    app_name: str
    description: str
    version: str
    api_key: Optional[str]

CONFIG = ConfigClass(
    app_name = name,
    description = description,
    version = version,
    api_key = getenv("API_KEY") if getenv("API_KEY") else None
)
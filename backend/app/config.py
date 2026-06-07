import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")


def optional_float(name):
    value = os.getenv(name, "").strip()
    return float(value) if value else None


def csv_list(name, default):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


DEFAULT_CORS_ALLOW_ORIGINS = (
    "http://127.0.0.1:5173,"
    "http://localhost:5173,"
    "http://127.0.0.1:8088,"
    "http://localhost:8088"
)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    JWT_EXP_SECONDS = int(os.getenv("JWT_EXP_SECONDS", "86400"))
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(INSTANCE_DIR / 'dispatch_dev.db').as_posix()}",
    )
    SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"
    SIMULATION_ENABLED = os.getenv("SIMULATION_ENABLED", "false").lower() == "true"
    SIMULATION_STEP_SECONDS = int(os.getenv("SIMULATION_STEP_SECONDS", "5"))
    MAP_UNIT_TO_KM = float(os.getenv("MAP_UNIT_TO_KM", "0.0065"))
    MAP_SCALE_METERS = int(os.getenv("MAP_SCALE_METERS", "50"))
    MAP_METERS_PER_UNIT = float(os.getenv("MAP_METERS_PER_UNIT", "6.5"))
    MAP_GPS_NORTH = optional_float("MAP_GPS_NORTH")
    MAP_GPS_SOUTH = optional_float("MAP_GPS_SOUTH")
    MAP_GPS_EAST = optional_float("MAP_GPS_EAST")
    MAP_GPS_WEST = optional_float("MAP_GPS_WEST")
    WECOM_DRY_RUN = os.getenv("WECOM_DRY_RUN", "true").lower() == "true"
    WECOM_CORP_ID = os.getenv("WECOM_CORP_ID", "")
    WECOM_AGENT_ID = os.getenv("WECOM_AGENT_ID", "")
    WECOM_SECRET = os.getenv("WECOM_SECRET", "")
    CORS_ALLOW_ORIGIN = os.getenv("CORS_ALLOW_ORIGIN", "")
    CORS_ALLOW_ORIGINS = sorted(set(csv_list("CORS_ALLOW_ORIGINS", DEFAULT_CORS_ALLOW_ORIGINS) + csv_list("CORS_ALLOW_ORIGIN", "")))

"""Settings."""

import logging as lg

import requests_cache

# core
STATIONS_ID_COL = "station_id"
TIME_COL = "time"
SJOIN_KWARGS = {"how": "inner", "predicate": "intersects"}

# ECV meteora nomenclature
# https://public.wmo.int/en/programmes/global-climate-observing-system/essential-climate-variables
# precipitation
ECV_PRECIPITATION = "precipitation"  # Precipitation
# pressure
ECV_PRESSURE = "pressure"  # Pressure (surface)
# radiation budget
ECV_RADIATION_SHORTWAVE = "radiation_shortwave"  # Incoming short-wave radiation
ECV_RADIATION_LONGWAVE_INCOMING = (
    "radiation_longwave_incoming"  # Incoming long-wave radiation
)
ECV_RADIATION_LONGWAVE_OUTGOING = (
    "radiation_longwave_outgoing"  # Outgoing long-wave radiation
)
# temperature
ECV_TEMPERATURE = "temperature"  # Air temperature (usually at 2m above ground)
# water vapour
ECV_DEW_POINT_TEMPERATURE = (
    "dew_point_temperature"  # Dew point temperature (usually at 2m above ground)
)
ECV_RELATIVE_HUMIDITY = "relative_humidity"  # Water vapour/relative humidity
# wind
ECV_WIND_SPEED = "wind_speed"  # Surface wind speed
ECV_WIND_DIRECTION = "wind_direction"  # Surface wind direction

# canonical units for ECVs (xclim/pint compatible)
ECV_UNIT_DICT = {
    ECV_PRECIPITATION: "mm",
    ECV_PRESSURE: "hPa",
    ECV_RADIATION_SHORTWAVE: "W m-2",
    ECV_RADIATION_LONGWAVE_INCOMING: "W m-2",
    ECV_RADIATION_LONGWAVE_OUTGOING: "W m-2",
    ECV_TEMPERATURE: "degC",
    ECV_DEW_POINT_TEMPERATURE: "degC",
    ECV_RELATIVE_HUMIDITY: "percent",
    ECV_WIND_SPEED: "m s-1",
    ECV_WIND_DIRECTION: "degree",
}

## netatmo
NETATMO_ON_GET_ERROR = "log"  # or "raise"

# qc
ATMOSPHERIC_LAPSE_RATE = 0.0065
OUTLIER_LOW_ALPHA = 0.01
OUTLIER_HIGH_ALPHA = 0.95
STATION_OUTLIER_THRESHOLD = 0.2
STATION_INDOOR_CORR_THRESHOLD = 0.9
UNRELIABLE_THRESHOLD = 0.2

# utils
## meteo
HEATWAVE_T_THRESHOLD = 25
HEATWAVE_N_CONSECUTIVE_DAYS = 3
HEATWAVE_STATION_AGG_FUNC = "mean"
HEATWAVE_INTER_STATION_AGG_FUNC = "mean"

REQUEST_KWARGS = {}
# PAUSE = 1
ERROR_PAUSE = 60
# TIMEOUT = 180
## cache
USE_CACHE = True
CACHE_NAME = "meteora-cache"
CACHE_BACKEND = "sqlite"
CACHE_EXPIRE = requests_cache.NEVER_EXPIRE

## logging
LOG_CONSOLE = False
LOG_FILE = False
LOG_FILENAME = "meteora"
LOG_LEVEL = lg.INFO
LOG_NAME = "meteora"
LOGS_FOLDER = "./logs"

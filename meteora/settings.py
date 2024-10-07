"""Settings."""

import logging as lg

import requests_cache

# core
# STATIONS_ID_NAME = "station_id"
TIME_NAME = "time"
SJOIN_KWS = {"how": "inner", "predicate": "intersects"}

# utils
REQUEST_KWS = {}
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

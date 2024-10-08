"""Agrometeo client."""

from typing import Any, List, Mapping, Union

import pandas as pd
import pyproj

from meteora import settings
from meteora.clients.base import BaseJSONClient, DateTimeType, RegionType
from meteora.mixins import AllStationsEndpointMixin, VariablesEndpointMixin

# API endpoints
BASE_URL = "https://agrometeo.ch/backend/api"
STATIONS_ENDPOINT = f"{BASE_URL}/stations"
VARIABLES_ENDPOINT = f"{BASE_URL}/sensors"
TS_ENDPOINT = f"{BASE_URL}/meteo/data"

# useful constants
LONLAT_CRS = pyproj.CRS("epsg:4326")
LV03_CRS = pyproj.CRS("epsg:21781")
# ACHTUNG: for some reason, the API mixes up the longitude and latitude columns ONLY in
# the CH1903/LV03 projection. This is why we need to swap the columns in the dict below.
GEOM_COL_DICT = {LONLAT_CRS: ["long_dec", "lat_dec"], LV03_CRS: ["lat_ch", "long_ch"]}
DEFAULT_CRS = LV03_CRS
# stations column used by the Agrometeo API (do not change)
STATIONS_API_ID_COL = "id"
# stations column used to index the data (e.g., time-series dataframe) by the client's
# class (can be any column that is unique to each station, e.g., name or id).
# The docstring would read as:
# stations_id_col : str, optional
#     Column of `stations_gdf` that will be used in the returned data frame to identify
#     the stations. If None, the value from `STATIONS_ID_COL` will be used.
# STATIONS_ID_COL = "name"
STATIONS_ID_COL = "id"
# variables name column
VARIABLES_NAME_COL = "name.en"
# variables code column
VARIABLES_ID_COL = "id"
# agrometeo sensors
# 42                       Leaf moisture III
# 43     Voltage of internal lithium battery
# 1              Temperature 2m above ground
# 4                       Relative humidity
# 6                           Precipitation
# 15              Intensity of precipitation
# 7                            Leaf moisture
# 11                         Solar radiation
# 41                           Solar Energie
# 9                          Avg. wind speed
# 14                         Max. wind speed
# 8                           Wind direction
# 22                       Temperature +10cm
# 12                    Luxmeter after Lufft
# 10                                ETP-Turc
# 24                              ETo-PenMon
# 13                               Dew point
# 18                       Real air pressure
# 2                    Soil temperature +5cm
# 19                  Soil temperature -20cm
# 3                   Soil temperature -10cm
# 5                       Soil moisture -5cm
# 20                   Pressure on sea level
# 17                        Leaf moisture II
# 25                     Soil moisture -30cm
# 26                     Soil moisture -50cm
# 39                                  unused
# 33                 Temperature in leafzone
# 32                         battery voltage
# 21                         min. wind speed
# 23                        Temperatur +20cm
# 27                  Temperatur in Pflanze1
# 28                  Temperatur in Pflanze1
# 29                                    UVAB
# 30                                     UVA
# 31                                     UAB
# 34                Air humidity in leafzone
# 35             Photosyth. active radiation
# 36                  Soil temperature -10cm
# 37                Temperatur 2m unbelüftet
# 38           elative Luftfeuchtigkeit +5cm
# 40                     Precip. Radolan Day
# 100                                   Hour
# 101                                   Year
# 102                            Day of year
# 103                           Degree hours
# 104                 Density of sporulation
# 105                           Leaf surface
ECV_DICT = {
    "precipitation": 6,  # "Precipitation",
    "pressure": 18,  # "Real air pressure",
    "surface_radiation_shortwave": 11,  # "Solar radiation",
    "surface_wind_speed": 9,  # "Avg. wind speed",
    "surface_wind_direction": 8,  # "Wind direction",
    "temperature": 1,  # "Temperature 2m above ground",
    "water_vapour": 4,  # "Relative humidity",
}
TIME_COL = "date"
API_DT_FMT = "%Y-%m-%d"
SCALE = "none"
MEASUREMENT = "avg"


class AgrometeoClient(AllStationsEndpointMixin, VariablesEndpointMixin, BaseJSONClient):
    """Agrometeo client."""

    # API endpoints
    _stations_endpoint = STATIONS_ENDPOINT
    _variables_endpoint = VARIABLES_ENDPOINT
    _ts_endpoint = TS_ENDPOINT

    # data frame labels constants
    _stations_id_col = STATIONS_ID_COL
    _variables_id_col = VARIABLES_ID_COL
    # _variables_name_col = VARIABLES_NAME_COL
    _ecv_dict = ECV_DICT
    _time_col = TIME_COL

    def __init__(
        self,
        region: RegionType,
        crs: Any = None,
        sjoin_kws: Union[Mapping, None] = None,
    ) -> None:
        """Initialize Agrometeo client."""
        # ACHTUNG: CRS must be either EPSG:4326 or EPSG:21781
        # ACHTUNG: CRS must be set before region
        if crs is not None:
            crs = pyproj.CRS(crs)
        else:
            crs = DEFAULT_CRS
        self.CRS = crs
        # self._variables_name_col = variables_name_col or VARIABLES_NAME_COL
        try:
            self.X_COL, self.Y_COL = GEOM_COL_DICT[self.CRS]
        except KeyError:
            raise ValueError(
                f"CRS must be among {list(GEOM_COL_DICT.keys())}, got {self.CRS}"
            )

        self.region = region
        if sjoin_kws is None:
            sjoin_kws = settings.SJOIN_KWS.copy()
        self.SJOIN_KWS = sjoin_kws

        # need to call super().__init__() to set the cache
        super().__init__()

    def _stations_df_from_content(self, response_content: dict) -> pd.DataFrame:
        return pd.DataFrame(response_content["data"]).set_index(self._stations_id_col)

    def _variables_df_from_content(self, response_content: dict) -> pd.DataFrame:
        variables_df = pd.json_normalize(response_content["data"])
        # ACHTUNG: need to strip strings, at least in variables name column. Note
        # that *it seems* that the integer type of variable code column is inferred
        # correctly
        variables_df[VARIABLES_NAME_COL] = variables_df[VARIABLES_NAME_COL].str.strip()
        return variables_df

    def _ts_params(self, variable_ids, start, end, scale=None, measurement=None):
        # process date args
        start_date = pd.Timestamp(start).strftime(API_DT_FMT)
        end_date = pd.Timestamp(end).strftime(API_DT_FMT)
        # process scale and measurement args
        if scale is None:
            # the API needs it to be lowercase
            scale = SCALE
        if measurement is None:
            measurement = MEASUREMENT

        _stations_ids = self.stations_gdf.index.astype(str)

        return {
            "from": start_date,
            "to": end_date,
            "scale": scale,
            "sensors": ",".join(
                f"{variable_id}:{measurement}" for variable_id in variable_ids
            ),
            "stations": ",".join(_stations_ids),
        }

    def _ts_df_from_content(self, response_content):
        # parse the response as a data frame
        ts_df = pd.json_normalize(response_content["data"]).set_index(self._time_col)
        ts_df.index = pd.to_datetime(ts_df.index)
        ts_df.index.name = self._time_col

        # ts_df.columns = self.stations_gdf[STATIONS_ID_COL]
        # ACHTUNG: note that agrometeo returns the data indexed by keys of the form
        # "{station_id}_{variable_code}_{measurement}". We can ignore the latter and
        # convert to a two-level (station, variable) multi index
        ts_df.columns = (
            ts_df.columns.str.split("_")
            .str[:-1]
            .map(tuple)
            .rename([self._stations_id_col, "variable"])
        )
        # convert station and variable ids to integer
        # ts_df.columns = ts_df.columns.set_levels(
        #     ts_df.columns.levels["station"].astype(int), level="station"
        # )
        for level_i, level_name in enumerate(ts_df.columns.names):
            ts_df.columns = ts_df.columns.set_levels(
                ts_df.columns.levels[level_i].astype(int), level=level_name
            )

        # convert to long form and return it
        return ts_df.stack(level=self._stations_id_col, future_stack=True).swaplevel()

    def get_ts_df(
        self,
        variables: Union[str, int, List[str], List[int]],
        start: DateTimeType,
        end: DateTimeType,
        *,
        scale: Union[str, None] = None,
        measurement: Union[str, None] = None,
    ) -> pd.DataFrame:
        """Get time series data frame.

        Parameters
        ----------
        variables : str, int or list-like of str or int
            Target variables, which can be either an Agrometeo variable code (integer or
            string), an essential climate variable (ECV) following the meteora
            nomenclature (string), or an Agrometeo variable name (string).
        start_date, end_date : str or datetime.date
            String in the "YYYY-MM-DD" format or datetime.date instance, respectively
            representing the start and end days of the requested data period.
        scale : None or {"hour", "day", "month", "year"}, default None
            Temporal scale of the measurements. The default value of None returns the
            finest scale, i.e., 10 minutes.
        measurement : None or {"min", "avg", "max"}, default None
            Whether the measurement values correspond to the minimum, average or maximum
            value for the required temporal scale. Ignored if `scale` is None.

        Returns
        -------
        ts_df : pd.DataFrame
            Data frame with a time series of meaurements (rows) at each station
            (columns).

        """
        return self._get_ts_df(
            variables, start, end, scale=scale, measurement=measurement
        )

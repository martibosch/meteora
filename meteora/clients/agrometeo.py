"""Agrometeo client."""

from collections.abc import Mapping, Sequence

import pandas as pd
import pyproj

from meteora import settings
from meteora.clients.base import BaseJSONClient
from meteora.mixins import StationsEndpointMixin, VariablesEndpointMixin
from meteora.utils import CRSType, DateTimeType, KwargsType, RegionType, VariablesType

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
STATIONS_GDF_ID_COL = "id"
TS_DF_STATIONS_ID_COL = "id"
TS_DF_TIME_COL = "date"
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
API_DT_FMT = "%Y-%m-%d"
SCALE = "none"
MEASUREMENT = "avg"


class AgrometeoClient(StationsEndpointMixin, VariablesEndpointMixin, BaseJSONClient):
    """Agrometeo client.

    Parameters
    ----------
    region : str, Sequence, GeoSeries, GeoDataFrame, PathLike, or IO
        The region to process. This can be either:

        -  A string with a place name (Nominatim query) to geocode.
        -  A sequence with the west, south, east and north bounds.
        -  A geometric object, e.g., shapely geometry, or a sequence of geometric
           objects. In such a case, the value will be passed as the `data` argument of
           the GeoSeries constructor, and needs to be in the same CRS as the one used by
           the client's class (i.e., the `CRS` class attribute).
        -  A geopandas geo-series or geo-data frame.
        -  A filename or URL, a file-like object opened in binary ('rb') mode, or a Path
           object that will be passed to `geopandas.read_file`.
    crs : str, dict or pyproj.CRS, optional
        The coordinate reference system (CRS) to be used. For Agrometeo, the
        provided value must be equivalent to either the EPSG:21781 (default) or
        EPSG:4326.
    sjoin_kwargs : dict, optional
        Keyword arguments to pass to the `geopandas.sjoin` function when filtering the
        stations within the region. If None, the value from `settings.SJOIN_KWARGS` is
        used.
    """

    # API endpoints
    _stations_endpoint = STATIONS_ENDPOINT
    _ts_endpoint = TS_ENDPOINT
    _variables_endpoint = VARIABLES_ENDPOINT

    # data frame labels constants
    _stations_gdf_id_col = STATIONS_GDF_ID_COL
    _ts_df_stations_id_col = TS_DF_STATIONS_ID_COL
    _ts_df_time_col = TS_DF_TIME_COL
    _variables_id_col = VARIABLES_ID_COL
    # _variables_name_col = VARIABLES_NAME_COL
    _ecv_dict = ECV_DICT

    def __init__(
        self,
        region: RegionType,
        *,
        crs: CRSType | None = None,
        **sjoin_kwargs: KwargsType,
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
        if sjoin_kwargs is None:
            sjoin_kwargs = settings.SJOIN_KWARGS.copy()
        self.SJOIN_KWARGS = sjoin_kwargs

        # need to call super().__init__() to set the cache
        super().__init__()

    def _stations_df_from_content(self, response_content: Mapping) -> pd.DataFrame:
        return pd.DataFrame(response_content["data"])

    def _variables_df_from_content(self, response_content: Mapping) -> pd.DataFrame:
        variables_df = pd.json_normalize(response_content["data"])
        # ACHTUNG: need to strip strings, at least in variables name column. Note
        # that *it seems* that the integer type of variable code column is inferred
        # correctly
        variables_df[VARIABLES_NAME_COL] = variables_df[VARIABLES_NAME_COL].str.strip()
        return variables_df

    def _ts_params(
        self,
        variable_ids: Sequence,
        start: DateTimeType,
        end: DateTimeType,
        scale: str | None = None,
        measurement: str | None = None,
    ) -> dict:
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

    def _ts_df_from_content(self, response_content: Mapping) -> pd.DataFrame:
        # parse the response as a data frame
        ts_df = pd.json_normalize(response_content["data"]).set_index(
            self._ts_df_time_col
        )
        ts_df.index = pd.to_datetime(ts_df.index)
        ts_df.index.name = self._ts_df_time_col

        # ts_df.columns = self.stations_gdf[STATIONS_ID_COL]
        # ACHTUNG: note that agrometeo returns the data indexed by keys of the form
        # "{station_id}_{variable_code}_{measurement}". We can ignore the latter and
        # convert to a two-level (station, variable) multi index
        ts_df.columns = (
            ts_df.columns.str.split("_")
            .str[:-1]
            .map(tuple)
            .rename([self._ts_df_stations_id_col, "variable"])
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
        return ts_df.stack(
            level=self._ts_df_stations_id_col, future_stack=True
        ).swaplevel()

    def get_ts_df(
        self,
        variables: VariablesType,
        start: DateTimeType,
        end: DateTimeType,
        *,
        scale: str | None = None,
        measurement: str | None = None,
    ) -> pd.DataFrame:
        """Get time series data frame.

        Parameters
        ----------
        variables : str, int or list-like of str or int
            Target variables, which can be either an Agrometeo variable code (integer or
            string) or an essential climate variable (ECV) following the Meteora
            nomenclature (string).
        start, end : datetime-like, str, int, float
            Values representing the start and end of the requested data period
            respectively. Accepts any datetime-like object that can be passed to
            pandas.Timestamp.
        scale : {"hour", "day", "month", "year"}, optional
            Temporal scale of the measurements. If None, returns the finest scale, i.e.,
            10 minutes.
        measurement : {"min", "avg", "max"}, optional
            Whether the measurement values correspond to the minimum, average or maximum
            value for the required temporal scale. If None, returns the average. Ignored
            if `scale` is None.

        Returns
        -------
        ts_df : pandas.DataFrame
            Long form data frame with a time series of measurements (second-level index)
            at each station (first-level index) for each variable (column).
        """
        ts_df = self._get_ts_df(
            variables, start, end, scale=scale, measurement=measurement
        )
        # filter time range, otherwise, for some reason, agrometeo API includes one day
        # after
        # TODO: dry with Meteocat, perhaps a global approach in the base client
        time_ser = ts_df.index.get_level_values(settings.TIME_COL).to_series()
        tz = time_ser.dt.tz
        return ts_df.loc[
            (
                slice(None),
                time_ser.between(
                    pd.Timestamp(start, tz=tz),
                    pd.Timestamp(end, tz=tz),
                    inclusive="both",
                ),
            ),
            :,
        ]

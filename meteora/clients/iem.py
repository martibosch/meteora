"""Iowa Environmental Mesonet (IEM) client."""

import abc
import io
from collections.abc import Sequence

import geopandas as gpd
import pandas as pd
import pyproj

from meteora import settings
from meteora.clients.base import (
    BaseTextClient,
    DateTimeType,
    KwargsType,
    RegionType,
    VariablesType,
)
from meteora.mixins import StationsEndpointMixin, VariablesHardcodedMixin

# API endpoints
BASE_URL = "https://mesonet.agron.iastate.edu"
# STATIONS_ENDPOINT = (
#     f"{BASE_URL}/sites/networks.php?special=allasos&format=csv&nohtml=on"
# )

# useful constants
STATIONS_ID_COL = "id"
VARIABLES_ID_COL = "code"
VARIABLES_LABEL_COL = "description"

# ASOS 1 minute https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?help
ONEMIN_STATIONS_ENDPOINT = f"{BASE_URL}/geojson/network/ASOS1MIN.geojson?only_online=0"
ONEMIN_TS_ENDPOINT = f"{BASE_URL}/cgi-bin/request/asos1min.py"
# tmpf: Air Temperature [F]
# dwpf: Dew Point Temperature [F]
# sknt: Wind Speed [knots]
# drct: Wind Direction
# gust_drct: 5 sec gust Wind Direction
# gust_sknt: 5 sec gust Wind Speed [knots]
# vis1_coeff: Visibility 1 Coefficient
# vis1_nd: Visibility 1 Night/Day
# vis2_coeff: Visibility 2 Coefficient
# vis2_nd: Visibility 2 Night/Day
# vis3_coeff: Visibility 3 Coefficient
# vis3_nd: Visibility 3 Night/Day
# ptype: Precip Type Code
# precip: 1 minute precip [inches]
# pres1: Sensor 1 Station Pressure [inches]
# pres2: Sensor 2 Station Pressure [inches]
# pres3: Sensor 3 Station Pressure [inches]
ONEMIN_VARIABLES_DICT = {
    "tmpf": "Air Temperature",
    "dwpf": "Dew Point Temperature",
    "sknt": "Wind Speed",
    "drct": "Wind Direction",
    "pres1": "Sensor 1 Station Pressure",
    "precip": "1 minute precip",
}
ONEMIN_ECV_DICT = {
    "precipitation": "precip",
    "pressure": "pres1",
    "surface_wind_speed": "sknt",
    "surface_wind_direction": "drct",
    "temperature": "tmpf",
}
ONEMIN_TIME_COL = "valid(UTC)"

# METAR/ASOS https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help
METAR_STATIONS_ENDPOINT = f"{BASE_URL}/geojson/network/AZOS.geojson"
METAR_TS_ENDPOINT = f"{BASE_URL}/cgi-bin/request/asos.py"
# see https://www.weather.gov/media/asos/aum-toc.pdf
# station: three or four character site identifier
# valid: timestamp of the observation
# tmpf: Air Temperature in Fahrenheit, typically @ 2 meters
# dwpf: Dew Point Temperature in Fahrenheit, typically @ 2 meters
# relh: Relative Humidity in %
# drct: Wind Direction in degrees from *true* north
# sknt: Wind Speed in knots
# p01i: One hour precipitation for the period from the observation time to the time of
#       the previous hourly precipitation reset. This varies slightly by site. Values
#       are in inches. This value may or may not contain frozen precipitation melted by
#       some device on the sensor or estimated by some other means. Unfortunately, we do
#       not know of an authoritative database denoting which station has which sensor.
# alti: Pressure altimeter in inches
# mslp: Sea Level Pressure in millibar
# vsby: Visibility in miles
# gust: Wind Gust in knots
# skyc1: Sky Level 1 Coverage
# skyc2: Sky Level 2 Coverage
# skyc3: Sky Level 3 Coverage
# skyc4: Sky Level 4 Coverage
# skyl1: Sky Level 1 Altitude in feet
# skyl2: Sky Level 2 Altitude in feet
# skyl3: Sky Level 3 Altitude in feet
# skyl4: Sky Level 4 Altitude in feet
# wxcodes: Present Weather Codes (space separated)
# feel: Apparent Temperature (Wind Chill or Heat Index) in Fahrenheit
# ice_accretion_1hr: Ice Accretion over 1 Hour (inches)
# ice_accretion_3hr: Ice Accretion over 3 Hours (inches)
# ice_accretion_6hr: Ice Accretion over 6 Hours (inches)
# peak_wind_gust: Peak Wind Gust (from PK WND METAR remark) (knots)
# peak_wind_drct: Peak Wind Gust Direction (from PK WND METAR remark) (deg)
# peak_wind_time: Peak Wind Gust Time (from PK WND METAR remark)
# metar: unprocessed reported observation in METAR format
METAR_VARIABLES_DICT = {
    "tmpf": "Air Temperature",
    "dwpf": "Dew Point Temperature",
    "relh": "Relative Humidity",
    "sknt": "Wind Speed",
    "drct": "Wind Direction",
    "mslp": "Sea Level Pressure in millibar",
    "p01i": "1 minute precip",
}
METAR_ECV_DICT = {
    "precipitation": "p01i",
    "pressure": "mslp",
    "surface_wind_speed": "sknt",
    "surface_wind_direction": "drct",
    "temperature": "tmpf",
    "water_vapor": "relh",
}
METAR_TIME_COL = "valid"


class IEMClient(
    StationsEndpointMixin, VariablesHardcodedMixin, BaseTextClient, abc.ABC
):
    """Abstract Iowa Environmental Mesonet (IEM) client."""

    # geom constants
    CRS = pyproj.CRS("epsg:4326")

    # data frame label constants
    _stations_id_col = STATIONS_ID_COL
    _variables_id_col = VARIABLES_ID_COL
    _variables_label_col = VARIABLES_LABEL_COL

    def __init__(self, region: RegionType, **sjoin_kwargs: KwargsType) -> None:
        """Initialize Iowa Environmental Mesonet (IEM) client.

        Parameters
        ----------
        region : str, Sequence, GeoSeries, GeoDataFrame, PathLike, or IO
            The region to process. This can be either:
            -  A string with a place name (Nominatim query) to geocode.
            -  A sequence with the west, south, east and north bounds.
            -  A geometric object, e.g., shapely geometry, or a sequence of geometric
               objects. In such a case, the value will be passed as the `data` argument
               of the GeoSeries constructor, and needs to be in the same CRS as the one
               used by the client's class (i.e., the `CRS` class attribute).
            -  A geopandas geo-series or geo-data frame.
            -  A filename or URL, a file-like object opened in binary ('rb') mode, or a
               Path object that will be passed to `geopandas.read_file`.
        sjoin_kwargs : dict, optional
            Keyword arguments to pass to the `geopandas.sjoin` function when filtering
            the stations within the region. If None, the value from
            `settings.SJOIN_KWARGS` is used.
        """
        self.region = region
        if sjoin_kwargs is None:
            sjoin_kwargs = settings.SJOIN_KWARGS.copy()
        self.SJOIN_KWARGS = sjoin_kwargs

        # need to call super().__init__() to set the cache
        super().__init__()

    def _get_stations_gdf(self) -> gpd.GeoDataFrame:
        """Get a GeoDataFrame featuring the stations data for the given region.

        Returns
        -------
        stations_gdf : gpd.GeoDataFrame
            The stations data for the given region as a GeoDataFrame.

        """
        # ACHTUNG: here we "bypass" `self._get_stations_df` because the stations are
        # provided as GeoJSON
        stations_gdf = gpd.read_file(self._stations_endpoint)
        # filter the stations
        # TODO: do we need to copy the dict to avoid reference issues?
        _sjoin_kwargs = self.SJOIN_KWARGS.copy()
        # predicate = _sjoin_kws.pop("predicate", SJOIN_PREDICATE)
        return stations_gdf.sjoin(self.region[["geometry"]], **_sjoin_kwargs)[
            stations_gdf.columns
        ]

    def _ts_params(
        self, variable_ids: Sequence, start: DateTimeType, end: DateTimeType
    ) -> dict:
        # process date args
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)

        return {
            "year1": start.year,
            "month1": start.month,
            "day1": start.day,
            "year2": end.year,
            "month2": end.month,
            "day2": end.day,
            self._vars_param: ",".join(variable_ids),
            "station": ",".join(self.stations_gdf[self._stations_id_col]),
        }

    def _ts_df_from_content(self, response_content: io.StringIO) -> pd.DataFrame:
        ts_df = pd.read_csv(
            response_content,
            na_values="M",
        )
        return (
            ts_df.assign(**{self._time_col: pd.to_datetime(ts_df[self._time_col])})
            .groupby(["station", self._time_col])
            .first(skipna=True)
        )

    def _post_process_ts_df(self, ts_df: pd.DataFrame) -> pd.DataFrame:
        # In this case:
        # - avoid sorting on index as data is already sorted
        # - avoid to_numeric as data is already numeric
        return ts_df

    def get_ts_df(
        self,
        variables: VariablesType,
        start: DateTimeType,
        end: DateTimeType,
    ) -> pd.DataFrame:
        """Get time series data frame for a given station.

        Parameters
        ----------
        variables : str, int or list-like of str or int
            Target variables, which can be either an IEM variable code (integer or
            string) or an essential climate variable (ECV) following the Meteora
            nomenclature (string).
        start, end : datetime-like, str, int, float
            Values representing the start and end of the requested data period
            respectively. Accepts any datetime-like object that can be passed to
            pandas.Timestamp.

        Returns
        -------
        ts_df : pandas.DataFrame
            Long form data frame with a time series of measurements (second-level index)
            at each station (first-level index) for each variable (column).
        """
        return self._get_ts_df(variables, start, end)


class ASOSOneMinIEMClient(IEMClient):
    """ASOS 1 minute Iowa Environmental Mesonet (IEM) client."""

    # API endpoints
    _stations_endpoint = ONEMIN_STATIONS_ENDPOINT
    _ts_endpoint = ONEMIN_TS_ENDPOINT

    # data frame labels constants
    _variables_dict = ONEMIN_VARIABLES_DICT
    _ecv_dict = ONEMIN_ECV_DICT
    _time_col = ONEMIN_TIME_COL
    _vars_param = "vars"


class METARASOSIEMClient(IEMClient):
    """METAR/ASOS Iowa Environmental Mesonet (IEM) client."""

    # API endpoints
    _stations_endpoint = METAR_STATIONS_ENDPOINT
    _ts_endpoint = METAR_TS_ENDPOINT

    # data frame labels constants
    _variables_dict = METAR_VARIABLES_DICT
    _ecv_dict = METAR_ECV_DICT
    _time_col = METAR_TIME_COL
    _vars_param = "data"

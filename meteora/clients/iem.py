"""Iowa Environmental Mesonet (IEM) client."""

import abc
from typing import Mapping, Union

import geopandas as gpd
import pandas as pd
import pyproj

from meteora import settings
from meteora.clients.base import BaseTextClient, DateTimeType, RegionType
from meteora.mixins import AllStationsEndpointMixin, VariablesHardcodedMixin

# API endpoints
BASE_URL = "https://mesonet.agron.iastate.edu"
# STATIONS_ENDPOINT = (
#     f"{BASE_URL}/sites/networks.php?special=allasos&format=csv&nohtml=on"
# )

# useful constants
STATIONS_ID_COL = "id"
VARIABLES_ID_COL = "code"
# VARIABLES_NAME_COL = "name"

# ASOS 1 minute https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?help
ONEMIN_STATIONS_ENDPOINT = f"{BASE_URL}/geojson/network/ASOS1MIN.geojson?only_online=0"
ONEMIN_TIME_SERIES_ENDPOINT = f"{BASE_URL}/cgi-bin/request/asos1min.py"
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
METAR_TIME_SERIES_ENDPOINT = f"{BASE_URL}/cgi-bin/request/asos.py"
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
# wxcodes: Present Weather Codes (space seperated)
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
    AllStationsEndpointMixin, VariablesHardcodedMixin, BaseTextClient, abc.ABC
):
    """Abstract Iowa Environmental Mesonet (IEM) client."""

    CRS = pyproj.CRS("epsg:4326")
    _stations_id_col = STATIONS_ID_COL
    _variables_id_col = VARIABLES_ID_COL
    # _variables_name_col = VARIABLES_NAME_COL

    def __init__(
        self, region: RegionType, sjoin_kws: Union[Mapping, None] = None
    ) -> None:
        """Initialize ASOS 1 minute Iowa Environmental Mesonet (IEM) client."""
        self.region = region
        if sjoin_kws is None:
            sjoin_kws = settings.SJOIN_KWS.copy()
        self.SJOIN_KWS = sjoin_kws

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
        _sjoin_kws = self.SJOIN_KWS.copy()
        # predicate = _sjoin_kws.pop("predicate", SJOIN_PREDICATE)
        return stations_gdf.sjoin(self.region[["geometry"]], **_sjoin_kws)[
            stations_gdf.columns
        ]

    def _time_series_params(self, variable_ids, start, end):
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

    def _ts_df_from_content(self, response_content):
        return (
            pd.read_csv(
                response_content,
                na_values="M",
            )
            .groupby(["stations", self._time_col])
            .first(skipna=True)
        )

    def _post_process_ts_df(self, ts_df):
        # In this case:
        # - avoid sorting on index as data is already sorted
        # - avoid to_numeric as data is already numeric
        return ts_df

    def get_ts_df(
        self,
        variables: Union[str, list[str]],
        start: DateTimeType,
        end: DateTimeType,
    ) -> pd.DataFrame:
        """Get time series data frame for a given station.

        Parameters
        ----------
        variables : str, int or list-like of str or int
            Target variables, which can be either an IEM variable code (integer or
            string), an essential climate variable (ECV) following the meteora
            nomenclature (string), or an agrometeo variable name (string).
        start_date, end_date : str or datetime.date
            String in the "YYYY-MM-DD" format or datetime.date instance, respectively
            representing the start and end days of the requested data period.

        Returns
        -------
        ts_df : pd.DataFrame
            Data frame with a time series of meaurements (rows) at each station
            (columns).

        """
        return self._get_ts_df(variables, start, end)


class ASOSOneMinIEMClient(IEMClient):
    """ASOS 1 minute Iowa Environmental Mesonet (IEM) client."""

    _stations_endpoint = ONEMIN_STATIONS_ENDPOINT
    _time_series_endpoint = ONEMIN_TIME_SERIES_ENDPOINT
    _variables_dict = ONEMIN_VARIABLES_DICT
    _ecv_dict = ONEMIN_ECV_DICT
    _time_col = ONEMIN_TIME_COL
    _vars_param = "vars"


class METARASOSIEMClient(IEMClient):
    """METAR/ASOS Iowa Environmental Mesonet (IEM) client."""

    _stations_endpoint = METAR_STATIONS_ENDPOINT
    _time_series_endpoint = METAR_TIME_SERIES_ENDPOINT
    _variables_dict = METAR_VARIABLES_DICT
    _ecv_dict = METAR_ECV_DICT
    _time_col = METAR_TIME_COL
    _vars_param = "data"

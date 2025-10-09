"""National Oceanic And Atmospheric Administration (NOAA) client."""

import logging as lg
from collections.abc import Iterable, Mapping, Sequence

import dask
import pandas as pd
import pooch
import pyproj
import requests
from dask import diagnostics

from meteora import settings, utils
from meteora.clients.base import BaseTextClient
from meteora.mixins import (
    MultiRequestTSMixin,
    StationsEndpointMixin,
    VariablesHardcodedMixin,
)
from meteora.utils import DateTimeType, KwargsType, RegionType, VariablesType

# disable pooch warnings when providing `None` as "known_hash"
logger = pooch.get_logger()
logger.setLevel("WARNING")


# API endpoints
BASE_URL = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly"
GHCNH_STATIONS_ENDPOINT = f"{BASE_URL}/doc/ghcnh-station-list.csv"
TS_ENDPOINT = f"{BASE_URL}/access/by-year/" + "{year}/psv/GHCNh_{station_id}_{year}.psv"

# for pooch
# TODO: how often can it change? how to properly update it if it does?
STATIONS_LIST_KNOWN_HASH = (
    "6b837d8d953aa6ebc172755864e549518944e7bec15b2196ee191219587a96f5"
)

# useful constants
STATIONS_GDF_ID_COL = "GHCN_ID"
# ACHTUNG: note that in the time series data frame the station column label is "Station
# ID" whereas in the stations data frame it is "id".
TS_DF_STATIONS_ID_COL = "STATION"
TS_DF_TIME_COL = "DATE"
VARIABLES_ID_COL = "code"
VARIABLES_LABEL_COL = "description"

# see section "IV. List of elements/variable" and appendix A of the GHCNh documentation
# www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/
# ghcnh_DOCUMENTATION.pdf
VARIABLES_DICT = {
    "temperature": "2 meter (circa) Above Ground Level Air (dry bulb) Temperature (⁰C n"
    "to tenths)",
    "relative_humidity": "Depending on the source, relative humidity is either measured"
    " directly or calculated from air (dry bulb) temperature and dew point temperature "
    "(whole percent)",
    "station_level_pressure": "The pressure that is observed at a specific elevation "
    "and is the true barometric pressure of a location. It is the pressure exerted by "
    "the atmosphere at a point as a result of gravity acting upon the 'column' of air "
    "that lies directly above the point. (hPa)",
    "precipitation": "Total liquid precipitation (rain or melted snow). Totals are "
    "nominally for the hour, but may include intermediate reports within the hour. "
    "Please refer to Appendix B for important details on precipitation totals; a `T` in"
    " the measurement code column indicates a trace amount of precipitation "
    "(millimeters).",
    "wind_speed": "Wind speed (meters per second)",
    "wind_direction": "Wind Direction from true north using compass directions (e.g. "
    "360 = true north, 180 = south, 270 = west, etc.). Note: A direction of `000` is "
    "given for calm winds. (whole degrees)",
}
ECV_DICT = {
    # precipitation
    "preciptation": "precipitation",
    # pressure
    "pressure": "station_level_pressure",
    # temperature
    "temperature": "temperature",
    # water vapour
    "relative_humidity": "relative_humidity",
    # wind
    "wind_speed": "wind_speed",
    "wind_direction": "wind_direction",
}


class GHCNHourlyClient(StationsEndpointMixin, VariablesHardcodedMixin, BaseTextClient):
    """NOAA GHCN hourly client.

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
    pooch_kwargs : dict, optional
        Keyword arguments to pass to the `pooch.retrieve` function when downloading the
        stations time series data.
    sjoin_kwargs : dict, optional
        Keyword arguments to pass to the `geopandas.sjoin` function when filtering the
        stations within the region. If None, the value from `settings.SJOIN_KWARGS` is
        used.
    """

    # ACHTUNG: many constants are set in `GHCNH_STATIONS_COLUMNS` above
    # geom constants
    X_COL = "LONGITUDE"
    Y_COL = "LATITUDE"
    CRS = pyproj.CRS("epsg:4326")

    # API endpoints
    _stations_endpoint = GHCNH_STATIONS_ENDPOINT
    _ts_endpoint = TS_ENDPOINT

    # data frame labels constants
    _stations_gdf_id_col = STATIONS_GDF_ID_COL
    _ts_df_stations_id_col = TS_DF_STATIONS_ID_COL
    _ts_df_time_col = TS_DF_TIME_COL
    _variables_id_col = VARIABLES_ID_COL
    _variables_label_col = VARIABLES_LABEL_COL
    _variables_dict = VARIABLES_DICT
    _ecv_dict = ECV_DICT

    def __init__(
        self,
        region: RegionType,
        *,
        pooch_kwargs: KwargsType | None = None,
        **sjoin_kwargs: KwargsType,
    ) -> None:
        """Initialize GHCN hourly client."""
        self.region = region
        if sjoin_kwargs is None:
            sjoin_kwargs = settings.SJOIN_KWARGS.copy()
        self.SJOIN_KWARGS = sjoin_kwargs

        if pooch_kwargs is None:
            pooch_kwargs = {}
        self.pooch_kwargs = pooch_kwargs

        # need to call super().__init__() to set the cache
        super().__init__()

    def _get_stations_df(self) -> pd.DataFrame:
        """Get all stations."""
        try:
            # ACHTUNG: we are not using `self.pooch_kwargs` to set the path to download
            # files, because the stations file path can be reused independently of the
            # region, so it is useful to cache it globally
            stations_filepath = pooch.retrieve(
                self._stations_endpoint, STATIONS_LIST_KNOWN_HASH
            )
        except ValueError:
            # sha hash mismatch, probably because of updates in the station list
            stations_filepath = pooch.retrieve(self._stations_endpoint, None)
        return pd.read_csv(stations_filepath)

    def _ts_params(
        self, variable_ids: Sequence, start: DateTimeType, end: DateTimeType
    ) -> dict:
        # process date args
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)

        return dict(variable_ids=variable_ids, start=start, end=end)

    def _ts_df_from_endpoint(self, ts_params) -> pd.DataFrame:
        """Get time series data frame from endpoint."""
        # we override this method because we need a separate request for each station
        variable_cols = list(ts_params["variable_ids"])
        cols_to_keep = (
            [self._ts_df_stations_id_col] + [self._ts_df_time_col] + variable_cols
        )
        start = ts_params["start"]
        end = ts_params["end"]
        requested_years = set(range(start.year, end.year + 1))

        # def _process_station_ts_df(year, station_id):
        #     try:
        #         station_ts_filepath = pooch.retrieve(
        #             self._ts_endpoint.format(year=year, station_id=station_id),
        #             None,
        #             **self.pooch_kwargs,
        #         )
        #     except requests.HTTPError:
        #         return pd.DataFrame()
        #     ts_df = pd.read_csv(station_ts_filepath, sep="|")[cols_to_keep]
        #     ts_df[self._ts_df_time_col] = pd.to_datetime(ts_df[self._ts_df_time_col])
        #     return ts_df[ts_df[self._ts_df_time_col].between(start, end)]

        # ts_df = pd.concat(
        #     [
        #         _process_station_ts_df(year, station_id)
        #         for station_id in self.stations_gdf.index
        #         for year in requested_years
        #     ]
        # )

        # use dask to parallelize requests
        def _process_station_ts_df(year, station_id):
            try:
                station_ts_filepath = pooch.retrieve(
                    self._ts_endpoint.format(year=year, station_id=station_id),
                    None,
                    **self.pooch_kwargs,
                )
            except requests.HTTPError:
                # TODO: log?
                return pd.DataFrame()
            ts_df = pd.read_csv(station_ts_filepath, sep="|", usecols=cols_to_keep)
            ts_df[self._ts_df_time_col] = pd.to_datetime(ts_df[self._ts_df_time_col])
            return ts_df[ts_df[self._ts_df_time_col].between(start, end)]

        tasks = [
            dask.delayed(_process_station_ts_df)(year, station_id)
            for station_id in self.stations_gdf.index
            for year in requested_years
        ]
        with diagnostics.ProgressBar():
            ts_dfs = dask.compute(*tasks)

        try:
            return pd.concat([ts_df for ts_df in ts_dfs if not ts_df.empty]).set_index(
                [self._ts_df_stations_id_col, self._ts_df_time_col]
            )
        except ValueError:  # no objects to concatenate
            utils.log(
                "No data found for the requested period and stations, returning an ",
                level=lg.WARNING,
            )
            return pd.DataFrame(columns=variable_cols)

    def _post_process_ts_df(self, ts_df: pd.DataFrame) -> pd.DataFrame:
        # no need to sort the index given the way the data has been requested
        return ts_df.apply(pd.to_numeric, axis="columns")

    def get_ts_df(
        self,
        variables: VariablesType,
        start: DateTimeType,
        end: DateTimeType,
    ) -> pd.DataFrame:
        """Get time series data frame.

        Parameters
        ----------
        variables : str, int or list-like of str or int
            Target variables, which can be either an GHCNh variable code (string) or an
            essential climate variable (ECV) following the Meteora nomenclature
            (string).
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


class _MeteoSwissClient(MultiRequestTSMixin, GHCNHourlyClient):
    def _get_ts_request_list(self, ts_params: Mapping) -> Iterable:
        # we override this method because we need a separate request for each station
        # variable_cols = list(ts_params["variable_ids"])
        # cols_to_keep = (
        #     [self._ts_df_stations_id_col] + [self._ts_df_time_col] + variable_cols
        # )
        start = ts_params["start"]
        end = ts_params["end"]
        requested_years = set(range(start.year, end.year + 1))

        return [
            (station_id, year)
            for station_id in self.stations_gdf.index
            for year in requested_years
        ]

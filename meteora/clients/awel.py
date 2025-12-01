"""Office for Waste, Water, Energy and Air (AWEL) of the canton of Zurich."""

from collections.abc import Sequence
from datetime import date as dt_date

import pandas as pd
import pooch
import pyproj
import requests
from dateutil.relativedelta import relativedelta
from pyregeon import RegionType

from meteora import settings
from meteora.clients.base import BaseTextClient
from meteora.mixins import VariablesHardcodedMixin
from meteora.utils import DateTimeType, KwargsType, VariablesType

# disable pooch warnings when providing `None` as "known_hash"
logger = pooch.get_logger()
logger.setLevel("WARNING")

# API endpoints
TS_ENDPOINT = (
    "https://www.web.statistik.zh.ch/awel/LoRa/data/"
    "AWEL_Sensors_LoRa_{year}{month:02}.csv"
)

# useful constants
STATIONS_GDF_ID_COL = "sensor"
TS_DF_STATIONS_ID_COL = "sensor"
TS_DF_TIME_COL = "starttime"
VARIABLES_ID_COL = "code"
VARIABLES_LABEL_COL = "description"
# see https://www.web.statistik.zh.ch/awel/LoRa/data/datenbeschrieb.txt
SENSOR_HEIGHT_COL = "magl"


# see https://www.web.statistik.zh.ch/awel/LoRa/data/datenbeschrieb.txt
VARIABLES_DICT = {
    "temperature": "measured value air temperature (in °C)",
    "humidity": "measured value relative humidity (in%)",
}
ECV_DICT = {
    "temperature": "temperature",
    "relative_humidity": "humidity",
}


class AWELClient(VariablesHardcodedMixin, BaseTextClient):
    """AWEL client (canton of Zurich).

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
    sensor_height : {1, 1.8, 2, 2.5, 2.7, 3.5, 4}, default 2
        Sensor height (in m) above site location, must be a value among the following:
        1, 1.8, 2, 2.5, 2.7, 3.5, 4. The default value is 2 m.
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
    X_COL = "x"
    Y_COL = "y"
    CRS = pyproj.CRS("epsg:2056")

    # API endpoints
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
        sensor_height: float = 2,
        pooch_kwargs: KwargsType | None = None,
        **sjoin_kwargs: KwargsType,
    ) -> None:
        """Initialize GHCN hourly client."""
        self.region = region
        if sjoin_kwargs is None:
            sjoin_kwargs = settings.SJOIN_KWARGS.copy()
        self.SJOIN_KWARGS = sjoin_kwargs

        self._sensor_height = sensor_height

        if pooch_kwargs is None:
            pooch_kwargs = {}
        self.pooch_kwargs = pooch_kwargs

        # need to call super().__init__() to set the cache
        super().__init__()

    def _get_stations_df(self):
        today = dt_date.today()
        # since there is no stations endpoint, get the time series data from the most
        # recent month
        # while True:
        # ACHTUNG: ugly hardcoded
        max_months = 10
        for months in range(1, max_months):
            ts_df_date = today - relativedelta(months=months)
            try:
                latest_ts_df_filepath = pooch.retrieve(
                    self._ts_endpoint.format(
                        year=ts_df_date.year, month=ts_df_date.month
                    ),
                    None,
                    **self.pooch_kwargs,
                )
                break
            except requests.HTTPError:
                pass
        return (
            pd.read_csv(latest_ts_df_filepath, sep=";")
            .drop(columns=["starttime"] + list(self._variables_dict.keys()))
            .groupby("sensor")
            .first()
            .reset_index()
        )

    def _ts_params(
        self, variable_ids: Sequence, start: DateTimeType, end: DateTimeType
    ) -> dict:
        # TODO: DRY with noaa.GHCNHourlyClient?
        # process date args
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)

        return dict(variable_ids=variable_ids, start=start, end=end)

    def _ts_df_from_endpoint(self, ts_params) -> pd.DataFrame:
        """Get time series data frame from endpoint."""
        # TODO: DRY with noaa.GHCNHourlyClient?
        # we override this method because we need a separate request for each station
        variable_cols = list(ts_params["variable_ids"])
        cols_to_keep = (
            [self._ts_df_stations_id_col]
            + [self._ts_df_time_col, SENSOR_HEIGHT_COL]
            + variable_cols
        )

        def _process_month_ts_df(year, month):
            try:
                month_ts_filepath = pooch.retrieve(
                    self._ts_endpoint.format(year=year, month=month),
                    None,
                    **self.pooch_kwargs,
                )
            except requests.HTTPError:
                # TODO: log?
                return pd.DataFrame()
            ts_df = pd.read_csv(month_ts_filepath, sep=";", usecols=cols_to_keep)
            # filter sensor height
            ts_df = ts_df[ts_df[SENSOR_HEIGHT_COL] == self._sensor_height]
            # filter stations
            ts_df = ts_df[
                ts_df[self._ts_df_stations_id_col].isin(self.stations_gdf.index)
            ]
            # drop (station, time) duplicates (TODO: use first and reset_index?)
            ts_df = ts_df.groupby(
                [self._ts_df_stations_id_col, self._ts_df_time_col]
            ).head(1)
            # ensure datetime
            ts_df[self._ts_df_time_col] = pd.to_datetime(ts_df[self._ts_df_time_col])
            # filter time range
            return ts_df[ts_df[self._ts_df_time_col].between(start, end)]

        start = ts_params["start"]
        end = ts_params["end"]
        date_range = pd.date_range(start=start, end=end, freq="MS")
        if len(date_range) == 0:
            date_range = [start]
        ts_df = pd.concat(
            [_process_month_ts_df(date.year, date.month) for date in date_range]
        )
        # ts_df = ts_df[ts_df[self._ts_df_time_col].between(start, end)]
        return ts_df.set_index([self._ts_df_stations_id_col, self._ts_df_time_col])

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
            Target variables, which can be either an AWEL variable code (string) or an
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

"""MetOffice client."""

import datetime
from collections.abc import Mapping

import pandas as pd
import pyproj

from meteora import settings
from meteora.clients.base import BaseJSONClient
from meteora.mixins import (
    APIKeyParamMixin,
    StationsEndpointMixin,
    VariablesEndpointMixin,
)
from meteora.utils import KwargsType, RegionType, VariablesType

# API endpoints
BASE_URL = "http://datapoint.metoffice.gov.uk/public/data"
STATIONS_ENDPOINT = f"{BASE_URL}/val/wxobs/all/json/sitelist"
# TODO: support filtering by station id
VARIABLES_ENDPOINT = TS_ENDPOINT = f"{BASE_URL}/val/wxobs/all/json/all"

# useful constants
# ACHTUNG: in MetOffice, the station id col is "id" in the stations endpoint but "i" in
# the data endpoint
STATIONS_GDF_ID_COL = "id"
TS_DF_STATIONS_ID_COL = "i"
TS_DF_TIME_COL = "$"
VARIABLES_ID_COL = "name"
ECV_DICT = {
    # "precipitation": "prec",  # NO PRECIPITATION DATA IS PROVIDED
    "pressure": "P",
    "surface_wind_speed": "S",
    "surface_wind_direction": "D",
    "temperature": "T",
    "water_vapour": "H",
}


class MetOfficeClient(
    APIKeyParamMixin, StationsEndpointMixin, VariablesEndpointMixin, BaseJSONClient
):
    """MetOffice client."""

    # geom constants
    X_COL = "longitude"
    Y_COL = "latitude"
    CRS = pyproj.CRS("epsg:4326")

    # API endpoints
    _stations_endpoint = STATIONS_ENDPOINT
    _variables_endpoint = VARIABLES_ENDPOINT
    _ts_endpoint = TS_ENDPOINT

    # data frame labels constants
    _stations_gdf_id_col = STATIONS_GDF_ID_COL
    _ts_df_stations_id_col = TS_DF_STATIONS_ID_COL
    _ts_df_time_col = TS_DF_TIME_COL
    # _variables_name_col = VARIABLES_NAME_COL
    _variables_id_col = VARIABLES_ID_COL
    _ecv_dict = ECV_DICT

    # auth constants
    _api_key_param_name = "key"

    def __init__(
        self,
        region: RegionType,
        api_key: str,
        **sjoin_kwargs: KwargsType,
    ) -> None:
        """Initialize MetOffice client.

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
        api_key : str
            MetOffice API key.
        sjoin_kwargs : dict, optional
            Keyword arguments to pass to the `geopandas.sjoin` function when filtering
            the stations within the region. If None, the value from
            `settings.SJOIN_KWARGS` is used.
        """
        self.region = region
        self._api_key = api_key
        if sjoin_kwargs is None:
            sjoin_kwargs = settings.SJOIN_KWARGS.copy()
        self.SJOIN_KWARGS = sjoin_kwargs
        self.res_param_dict = {"res": "hourly"}

        # need to call super().__init__() to set the cache
        super().__init__()

    @property
    def request_params(self) -> dict:
        """Request parameters."""
        # TODO: would it be better to use a property setter?
        try:
            return self._request_params
        except AttributeError:
            self._request_params = super().request_params | self.res_param_dict
            return self._request_params

    def _stations_df_from_content(self, response_content: Mapping) -> pd.DataFrame:
        return pd.DataFrame(response_content["Locations"]["Location"])

    def _variables_df_from_content(self, response_content: Mapping) -> pd.DataFrame:
        return pd.DataFrame(response_content["SiteRep"]["Wx"]["Param"])

    @property
    def variables_df(self) -> pd.DataFrame:
        """Variables dataframe."""
        try:
            return self._variables_df
        except AttributeError:
            with self._session.cache_disabled():
                response_content = self._get_content_from_url(self._variables_endpoint)
            self._variables_df = self._variables_df_from_content(response_content)
            return self._variables_df

    def _ts_df_from_endpoint(self, ts_params: Mapping) -> pd.DataFrame:
        # perform request
        response_content = self._get_content_from_url(
            self._ts_endpoint, params=ts_params
        )

        # process response content into a time series data frame
        # ACHGUNG: we are only overriding this method to pass the extra positional
        # argument `variable_id_ser` to `_ts_df_from_content`
        return self._ts_df_from_content(response_content, ts_params["variable_ids"])

    def _ts_df_from_content(
        self, response_content: Mapping, variable_id_ser: pd.Series
    ) -> pd.DataFrame:
        # this is the time of the latest observation, from which the API returns the
        # latest 24 hours
        latest_obs_time = pd.Timestamp(response_content["SiteRep"]["DV"]["dataDate"])

        # now we get the data, which is provided for each station separately, and for
        # each of the days in which the previous 24h fall
        ts_list = response_content["SiteRep"]["DV"]["Location"]

        # ensure that we have a list even if there is only one location (in which case
        # the API returns a dict)
        if isinstance(ts_list, dict):
            ts_list = [ts_list]

        # process the response
        df = pd.json_normalize(ts_list)
        # first, filter by stations of interest
        df = df[df[self._ts_df_stations_id_col].isin(self.stations_gdf.index)]
        # process the observations in the filtered location
        ts_df = pd.concat(
            [
                pd.concat(
                    [
                        pd.DataFrame(obs_dict["Rep"])
                        for obs_dict in station_records[::-1]
                    ]
                ).assign(**{self._ts_df_stations_id_col: station_id})
                for station_id, station_records in df["Period"].items()
            ]
        )

        # compute the timestamp of each observation (the "$" column contains the minutes
        # before `latest_obs_time`
        ts_df[self._ts_df_time_col] = ts_df[self._ts_df_time_col].apply(
            lambda dt: latest_obs_time - datetime.timedelta(minutes=int(dt))
        )

        ts_df = ts_df
        # ignore errors in `to_numeric` because of wind direction "D" being letters
        for col in variable_id_ser:
            try:
                ts_df[col] = pd.to_numeric(ts_df[col])
            except ValueError:
                pass
        # select only target variable columns and convert into long data frame
        _index_cols = [self._ts_df_stations_id_col, self._ts_df_time_col]
        return (
            ts_df[variable_id_ser]
            .assign(**{_index_col: ts_df[_index_col] for _index_col in _index_cols})
            .pivot_table(index=_index_cols)
        )

    def get_ts_df(
        self,
        variables: VariablesType,
    ) -> pd.DataFrame:
        """Get time series data frame for the last 24h.

        Parameters
        ----------
        variables : str, int or list-like of str or int
            Target variables, which can be either a MetOffice variable code (integer or
            string) or an essential climate variable (ECV) following the Meteora
            nomenclature (string).

        Returns
        -------
        ts_df : pandas.DataFrame
            Long form data frame with a time series of measurements (second-level index)
            at each station (first-level index) for each variable (column).
        """
        # disable cache since the endpoint returns the latest 24h of data
        with self._session.cache_disabled():
            return self._get_ts_df(variables)

"""MetOffice client."""

import datetime
from typing import Mapping, Union

import pandas as pd
import pyproj

from meteora import settings
from meteora.clients.base import BaseJSONClient, RegionType, VariablesType
from meteora.mixins import (
    AllStationsEndpointMixin,
    APIKeyParamMixin,
    VariablesEndpointMixin,
)

# API endpoints
BASE_URL = "http://datapoint.metoffice.gov.uk/public/data"
STATIONS_ENDPOINT = f"{BASE_URL}/val/wxobs/all/json/sitelist"
# TODO: support filtering by station id
VARIABLES_ENDPOINT = TS_ENDPOINT = f"{BASE_URL}/val/wxobs/all/json/all"

# useful constants
# ACHTUNG: in MetOffice, the station id col is "id" in the stations endpoint but "i" in
# the data endpoint
STATIONS_ID_COL = "id"
VARIABLES_ID_COL = "name"
ECV_DICT = {
    # "precipitation": "prec",  # NO PRECIPITATION DATA IS PROVIDED
    "pressure": "P",
    "surface_wind_speed": "S",
    "surface_wind_direction": "D",
    "temperature": "T",
    "water_vapour": "H",
}
TIME_COL = "$"


class MetOfficeClient(
    APIKeyParamMixin, AllStationsEndpointMixin, VariablesEndpointMixin, BaseJSONClient
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
    _stations_id_col = STATIONS_ID_COL
    # _variables_name_col = VARIABLES_NAME_COL
    _variables_id_col = VARIABLES_ID_COL
    _ecv_dict = ECV_DICT
    _time_col = TIME_COL
    # ACHTUNG: in MetOffice, the station id col is "id" in the stations endpoint but "i"
    # in the time series endpoint
    _ts_station_id_col = "i"

    # auth constants
    _api_key_param_name = "key"

    def __init__(
        self,
        region: RegionType,
        api_key: str,
        sjoin_kws: Union[Mapping, None] = None,
        res_param: Union[str, None] = None,
    ) -> None:
        """Initialize MetOffice client."""
        self.region = region
        self._api_key = api_key
        if sjoin_kws is None:
            sjoin_kws = settings.SJOIN_KWS.copy()
        self.SJOIN_KWS = sjoin_kws
        if res_param is None:
            res_param = "hourly"
        self.res_param_dict = {"res": res_param}

        # need to call super().__init__() to set the cache
        super().__init__()

    @property
    def request_params(self):
        """Request parameters."""
        # TODO: would it be better to use a property setter?
        try:
            return self._request_params
        except AttributeError:
            self._request_params = super().request_params | self.res_param_dict
            return self._request_params

    def _stations_df_from_content(self, response_content: dict) -> pd.DataFrame:
        return pd.DataFrame(response_content["Locations"]["Location"])

    def _variables_df_from_content(self, response_content) -> pd.DataFrame:
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

    def _ts_df_from_content(self, response_content, variable_id_ser):
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
        df = df[
            df[self._ts_station_id_col].isin(
                self.stations_gdf[self._stations_id_col].values
            )
        ]
        # process the observations in the filtered location
        ts_df = pd.concat(
            [
                pd.concat(
                    [
                        pd.DataFrame(obs_dict["Rep"])
                        for obs_dict in station_records[::-1]
                    ]
                ).assign(**{self._ts_station_id_col: station_id})
                for station_id, station_records in df["Period"].items()
            ]
        )

        # compute the timestamp of each observation (the "$" column contains the minutes
        # before `latest_obs_time`
        ts_df["time"] = ts_df[self._time_col].apply(
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
        _index_cols = [self._ts_station_id_col, "time"]
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
            Long form data frame with a time series of meaurements (second-level index)
            at each station (first-level index) for each variable (column).
        """
        # ACHTUNG: we cannot reuse the base `_get_ts_df` method here because we need to
        # pass the list of variables to `_ts_df_from_content`.
        # TODO: explore if there is a better way to do this, e.g., `_ts_df_from_content`
        # takes no extra arguments but returns the data frame form that is most natural
        # to the API response, i.e., in this case, a "wide" data frame. Also maybe
        # implement mixins for clients which (unlike MetOffice) accept date range
        # arguments in the time series endpoint

        # process the variables arg
        variable_id_ser = self._get_variable_id_ser(variables)

        # prepare request
        ts_params = self._ts_params(variable_id_ser)

        # perform request
        # disable cache since the endpoint returns the latest 24h of data
        with self._session.cache_disabled():
            response_content = self._get_content_from_url(
                self._ts_endpoint, params=ts_params
            )

        # process response content into a time series data frame
        ts_df = self._ts_df_from_content(response_content, variable_id_ser)

        # TODO: the part below is embarrassingly DRY-able, i.e., hard copied from
        # `BaseClient._get_ts_df`
        # ensure that we return the variable column names as provided by the user in the
        # `variables` argument (e.g., if the user provided variable codes, use
        # variable codes in the column names).
        ts_df = self._rename_variables_cols(ts_df, variable_id_ser)

        # apply a generic post-processing function
        return self._post_process_ts_df(ts_df)

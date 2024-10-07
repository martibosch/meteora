"""MetOffice client."""

import datetime
from typing import List, Mapping, Union

import pandas as pd
import pyproj

from meteora import settings
from meteora.clients.base import BaseJSONClient, RegionType
from meteora.mixins import (
    AllStationsEndpointMixin,
    APIKeyParamMixin,
    VariablesEndpointMixin,
)

# API endpoints
BASE_URL = "http://datapoint.metoffice.gov.uk/public/data"
STATIONS_ENDPOINT = f"{BASE_URL}/val/wxobs/all/json/sitelist"
# TODO: support filtering by station id
VARIABLES_ENDPOINT = TIME_SERIES_ENDPOINT = f"{BASE_URL}/val/wxobs/all/json/all"

# useful constants
# ACHTUNG: in MetOffice, the station id col is "id" in the stations endpoint but "i" in
# the data endpoint
STATIONS_ID_COL = "id"
# TODO: actually, the variable name column is "$"
VARIABLES_ID_COL = "name"
ECV_DICT = {
    # "precipitation": "prec",  # NO PRECIPITATION DATA IS PROVIDED
    "pressure": "P",
    "surface_wind_speed": "S",
    "surface_wind_direction": "D",
    "temperature": "T",
    "water_vapour": "H",
}
# TIME_COL = ""  # THERE IS NO TIME COLUMN


class MetOfficeClient(
    APIKeyParamMixin, AllStationsEndpointMixin, VariablesEndpointMixin, BaseJSONClient
):
    """MetOffice client."""

    X_COL = "longitude"
    Y_COL = "latitude"
    CRS = pyproj.CRS("epsg:4326")
    _stations_endpoint = STATIONS_ENDPOINT
    _stations_id_col = STATIONS_ID_COL
    _variables_endpoint = VARIABLES_ENDPOINT
    # _variables_name_col = VARIABLES_NAME_COL
    _variables_id_col = VARIABLES_ID_COL
    _ecv_dict = ECV_DICT
    _time_series_endpoint = TIME_SERIES_ENDPOINT
    # ACHTUNG: in MetOffice, the station id col is "id" in the stations endpoint but "i"
    # in the time series endpoint
    _time_series_station_id_col = "i"
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
        self.request_params = {"res": res_param}

        # need to call super().__init__() to set the cache
        super().__init__()

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

    def _ts_df_from_content(self, response_content):
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
            df[self._time_series_station_id_col].isin(
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
                ).assign(**{self._time_serise_station_id_col: station_id})
                for station_id, station_records in df["Period"].items()
            ]
        )

        # compute the timestamp of each observation (the "$" column contains the minutes
        # before `latest_obs_time`
        ts_df["time"] = ts_df["$"].apply(
            lambda dt: latest_obs_time - datetime.timedelta(minutes=int(dt))
        )

        _index_cols = [self._time_series_station_id_col, "time"]
        # ts_df = ts_df[variable_ids]
        # convert into long data frame
        return (
            ts_df.apply(pd.to_numeric)
            .assign(**{_index_col: ts_df[_index_col] for _index_col in _index_cols})
            .pivot_table(index=_index_cols)
        )

    def get_ts_df(
        self,
        variables: Union[str, int, List[str], List[int]],
    ) -> pd.DataFrame:
        """Get time series data frame for the last 24h.

        Parameters
        ----------
        variables : str, int or list-like of str or int
            Target variables, which can be either a MetOffice variable code (integer or
            string), an essential climate variable (ECV) following the meteora
            nomenclature (string), or a MetOffice variable name (string).

        Returns
        -------
        ts_df : pd.DataFrame
            Data frame with a time series of meaurements (rows) at each station
            (columns).

        """
        # disable cache since the endpoint returns the latest 24h of data
        with self._session.cache_disabled():
            return self._get_ts_df(variables)

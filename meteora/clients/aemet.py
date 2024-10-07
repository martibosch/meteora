"""AEMET client."""

from typing import List, Mapping, Union

import pandas as pd
import pyproj

from meteora import settings, utils
from meteora.clients.base import BaseJSONClient, RegionType
from meteora.mixins import (
    AllStationsEndpointMixin,
    APIKeyParamMixin,
    VariablesEndpointMixin,
)

# API endpoints
BASE_URL = "https://opendata.aemet.es/opendata/api"
STATIONS_ENDPOINT = (
    f"{BASE_URL}/valores/climatologicos/inventarioestaciones/todasestaciones"
)
VARIABLES_ENDPOINT = TIME_SERIES_ENDPOINT = f"{BASE_URL}/observacion/convencional/todas"

# useful constants
# ACHTUNG: in Aemet, the station id col is "indicativo" in the stations endpoint but
# "idema" in the data endpoint
STATIONS_ID_COL = "idema"
VARIABLES_ID_COL = "id"
ECV_DICT = {
    "precipitation": "prec",
    "pressure": "pres",
    "surface_wind_speed": "vv",
    "surface_wind_direction": "dv",
    "temperature": "ta",
    "water_vapour": "hr",
}
TIME_COL = "fint"


class AemetClient(
    APIKeyParamMixin,
    AllStationsEndpointMixin,
    VariablesEndpointMixin,
    BaseJSONClient,
):
    """MetOffice client."""

    X_COL = "longitud"
    Y_COL = "latitud"
    CRS = pyproj.CRS("epsg:4326")
    _stations_endpoint = STATIONS_ENDPOINT
    _stations_id_col = STATIONS_ID_COL
    _variables_endpoint = VARIABLES_ENDPOINT
    # _variables_name_col = VARIABLES_NAME_COL
    _variables_id_col = VARIABLES_ID_COL
    _ecv_dict = ECV_DICT
    _time_series_endpoint = TIME_SERIES_ENDPOINT
    _time_col = TIME_COL
    _api_key_param_name = "api_key"
    request_headers = {"cache-control": "no-cache"}

    # @property
    # def request_headers(self):
    #     """Request headers."""
    #     return {"cache-control": "no-cache"}

    def __init__(
        self, region: RegionType, api_key: str, sjoin_kws: Union[Mapping, None] = None
    ) -> None:
        """Initialize MetOffice client."""
        self.region = region
        self._api_key = api_key
        if sjoin_kws is None:
            sjoin_kws = settings.SJOIN_KWS.copy()
        self.SJOIN_KWS = sjoin_kws
        # need to call super().__init__() to set the cache
        super().__init__()

    def _stations_df_from_content(self, response_content: dict) -> pd.DataFrame:
        # response_content returns a dict with urls, where the one under the "datos" key
        # contains the JSON data
        stations_df = pd.read_json(response_content["datos"], encoding="latin1")
        for col in [self.X_COL, self.Y_COL]:
            stations_df[col] = utils.dms_to_decimal(stations_df[col])
        return stations_df

    def _variables_df_from_content(self, response_json) -> pd.DataFrame:
        return pd.json_normalize(
            pd.read_json(response_json["metadatos"], encoding="latin1")["campos"]
        )

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
        # response_content returns a dict with urls, where the one under the "datos" key
        # contains the JSON data
        ts_df = pd.read_json(response_content["datos"], encoding="latin1")
        # filter only stations from the region
        # TODO: how to handle better the "indicativo" column name? i.e., the stations id
        # column is "idema" in the observation data frame but "indicativo" in the
        # stations data frame.
        return ts_df[ts_df[self._stations_id_col].isin(self.stations_gdf["indicativo"])]

    def get_ts_df(
        self,
        variables: Union[str, int, List[str], List[int]],
    ) -> pd.DataFrame:
        """Get time series data frame for the last 24h.

        Parameters
        ----------
        variables : str, int or list-like of str or int
            Target variables, which can be either an AEMET variable code (integer or
            string), an essential climate variable (ECV) following the meteora
            nomenclature (string), or an agrometeo variable name (string).

        Returns
        -------
        ts_df : pd.DataFrame
            Data frame with a time series of meaurements (rows) at each station
            (columns).

        """
        # disable cache since the endpoint returns the latest 24h of data
        with self._session.cache_disabled():
            return self._get_ts_df(variables)

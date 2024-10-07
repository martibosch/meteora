"""Meteocat client."""

import datetime
from typing import List, Mapping, Union

import pandas as pd
import pyproj

from meteora import settings
from meteora.clients.base import BaseJSONClient, RegionType
from meteora.mixins import (
    AllStationsEndpointMixin,
    APIKeyHeaderMixin,
    VariablesEndpointMixin,
)

# API endpoints
BASE_URL = "https://api.meteo.cat/xema/v1"
STATIONS_ENDPOINT = f"{BASE_URL}/estacions/metadades"
VARIABLES_ENDPOINT = f"{BASE_URL}/variables/mesurades/metadades"
TIME_SERIES_ENDPOINT = f"{BASE_URL}/variables/mesurades"

# useful constants
STATIONS_ID_COL = "codi"
# VARIABLES_NAME_COL = "nom"
VARIABLES_ID_COL = "codi"
ECV_DICT = {
    "precipitation": 35,  # "Precipitació",
    "pressure": 34,  # "Pressió atmosfèrica",
    "surface_radiation_shortwave": 39,  # "Radiació UV",
    "surface_wind_speed": 46,  # "Velocitat del vent a 2 m (esc.)",
    "surface_wind_direction": 47,  # "Direcció de vent 2 m (m. 1)",
    "temperature": 32,  # "Temperatura",
    "water_vapour": 33,  # "Humitat relativa",
}
TIME_COL = "data"


class MeteocatClient(
    APIKeyHeaderMixin,
    AllStationsEndpointMixin,
    VariablesEndpointMixin,
    BaseJSONClient,
):
    """Meteocat client."""

    X_COL = "coordenades.longitud"
    Y_COL = "coordenades.latitud"
    CRS = pyproj.CRS("epsg:4326")
    _stations_endpoint = STATIONS_ENDPOINT
    _stations_id_col = STATIONS_ID_COL
    _variables_endpoint = VARIABLES_ENDPOINT
    # _variables_name_col = VARIABLES_NAME_COL
    _variables_id_col = VARIABLES_ID_COL
    _ecv_dict = ECV_DICT
    _time_series_endpoint = TIME_SERIES_ENDPOINT
    _time_col = TIME_COL

    def __init__(
        self, region: RegionType, api_key: str, sjoin_kws: Union[Mapping, None] = None
    ) -> None:
        """Initialize Meteocat client."""
        self.region = region
        self._api_key = api_key
        if sjoin_kws is None:
            sjoin_kws = settings.SJOIN_KWS.copy()
        self.SJOIN_KWS = sjoin_kws

        # need to call super().__init__() to set the cache
        super().__init__()

    def _stations_df_from_content(self, response_content: dict) -> pd.DataFrame:
        return pd.json_normalize(response_content)

    def _variables_df_from_content(self, response_content: dict) -> pd.DataFrame:
        return pd.json_normalize(response_content)

    def _get_ts_df(
        self,
        variable_id: int,
        date: datetime.date,
    ) -> pd.DataFrame:
        """Get time series data frame for a given day.

        Parameters
        ----------
        variable_id : int
            Meteocat variable code.
        date : datetime.date
            datetime.date instance for the requested data period.

        Returns
        -------
        ts_df : pd.DataFrame
            Data frame with a time series of meaurements (rows) at each station
            (columns).

        """
        # # process date arg
        # if isinstance(date, str):
        #     date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        # request url
        request_url = (
            f"{self._time_series_endpoint}"
            f"/{variable_id}/{date.year}/{date.month:02}/{date.day:02}"
        )
        response_content = self._get_content_from_url(request_url)
        # process response
        response_df = pd.json_normalize(response_content)
        # filter stations
        response_df = response_df[
            response_df["codi"].isin(self.stations_gdf[self._stations_id_col])
        ]
        # extract json observed data, i.e.,  the "variables" column into a list of data
        # frames and concatenate them into a single data frame
        ts_df = pd.concat(
            response_df.apply(
                lambda row: pd.DataFrame(row["variables"][0]["lectures"]), axis=1
            ).tolist()
        )
        # add the station id column matching the observations
        ts_df[self._stations_id_col] = (
            response_df[self._stations_id_col]
            .repeat(
                response_df.apply(
                    lambda row: len(row["variables"][0]["lectures"]), axis=1
                )
            )
            .values
        )
        # TODO: values_col as class-level constant?
        values_col = "valor"
        # # convert to a wide data frame
        # ts_df = long_df.pivot_table(
        #     index=self._time_col, columns=self._stations_id_col, values=values_col
        # )
        # # set the index name
        # ts_df.index.name = settings.TIME_NAME
        # # convert the index from string to datetime
        # ts_df.index = pd.to_datetime(ts_df.index)
        # ACHTUNG: do not sort the index here
        # note that we are renaming a series
        return (
            ts_df.assign(**{self._time_col: pd.to_datetime(ts_df[self._time_col])})
            .set_index([self._stations_id_col, self._time_col])[values_col]
            .rename(variable_id)
        )

    def get_ts_df(
        self,
        variables: Union[str, int, List[str], List[int]],
        start_date: Union[str, datetime.date],
        end_date: Union[str, datetime.date],
    ) -> pd.DataFrame:
        """Get time series data frame.

        Parameters
        ----------
        variable : str or int
            Target variables, which can be either a Meteocat variable code (integer or
            string), an essential climate variable (ECV) following the meteora
            nomenclature (string), or a Meteocat variable name (string).
        start_date, end_date : str or datetime.date
            String in the "YYYY-MM-DD" format or datetime.date instance, respectively
            representing the start and end days of the requested data period.

        Returns
        -------
        ts_df : pd.DataFrame
            Data frame with a time series of meaurements (rows) at each station
            (columns).

        """
        # process variables
        # ensure variable codes have the same dtype as in the variables data frame
        variable_ids = pd.Series(
            self._get_variable_ids(variables),
            dtype=self.variables_df[self._variables_id_col].dtype,
        )

        # return self._get_ts_df(variable, date)
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")

        # ensure that we return the variable column names as provided by the user in the
        # `variables` argument (e.g., if the user provided variable codes, use
        # variable codes in the column names).
        # TODO: avoid this if the user provided variable codes (in which case the dict
        # maps variable codes to variable codes)?
        variable_label_dict = {
            variable_id: variable
            for variable_id, variable in zip(variable_ids, variables)
        }
        return (
            pd.concat(
                [
                    pd.concat(
                        [
                            self._get_ts_df(variable_id, date)
                            for variable_id in variable_ids
                        ],
                        axis="columns",
                        ignore_index=False,
                    )
                    for date in date_range
                ],
                axis="index",
                ignore_index=False,
            )
            .rename(columns=variable_label_dict)
            .sort_index()
        )

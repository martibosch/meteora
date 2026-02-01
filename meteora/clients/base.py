"""Base abstract classes for meteo station datasets."""

import abc
import io
import logging as lg
import re
import time
from collections.abc import Mapping

import geopandas as gpd
import pandas as pd
import pooch
import pyproj
import requests
import requests_cache
from pyregeon import RegionMixin, RegionType

from meteora import settings, units, utils
from meteora.utils import KwargsType, VariablesType

__all__ = [
    "BaseFileClient",
    "BaseJSONClient",
    "BaseRequestClient",
    "BaseTextClient",
]


class BaseClient(RegionMixin, abc.ABC):
    """Meteora base client."""

    def __init__(self, *args, **kwargs):
        # if use_cache is None:
        #     use_cache = settings.USE_CACHE
        if settings.USE_CACHE:  # if use_cache:
            session = requests_cache.CachedSession(
                cache_name=settings.CACHE_NAME,
                backend=settings.CACHE_BACKEND,
                expire_after=settings.CACHE_EXPIRE,
            )
        else:
            session = requests.Session()
        self._session = session

    @utils.abstract_attribute
    def X_COL(self) -> str:  # pylint: disable=invalid-name
        """Name of the column with longitude coordinates."""
        pass

    @utils.abstract_attribute
    def Y_COL(self) -> str:  # pylint: disable=invalid-name
        """Name of the column with latitude coordinates."""
        pass

    @utils.abstract_attribute
    def CRS(self) -> pyproj.CRS:  # pylint: disable=invalid-name
        """CRS of the data source."""
        pass

    @RegionMixin.region.setter
    def region(self, region: RegionType):
        # call parent's setter
        RegionMixin.region.fset(self, region)
        # ensure that region is in the client's CRS
        self._region = self._region.to_crs(self.CRS)

    @utils.abstract_attribute
    def _stations_gdf_id_col(self) -> str:
        """Column with the station IDs in the `stations_gdf` returned by the API."""
        pass

    @utils.abstract_attribute
    def _ts_df_time_col(self) -> str:
        """Column with the timestamps in the `ts_df` returned by the API."""
        pass

    @utils.abstract_attribute
    def _ts_df_stations_id_col(self) -> str:
        """Column with the station IDs in the `ts_df` returned by the API."""
        pass

    @utils.abstract_attribute
    def _variables_id_col(self) -> str:
        pass

    @utils.abstract_attribute
    def _ecv_dict(self) -> dict:
        pass

    @property
    def request_headers(self) -> dict:
        """Request headers."""
        return {}

    @property
    def request_params(self) -> dict:
        """Request parameters."""
        return {}

    # stations
    def _get_stations_gdf(self) -> gpd.GeoDataFrame:
        """Get a GeoDataFrame featuring the stations data for the given region.

        Returns
        -------
        stations_gdf : gpd.GeoDataFrame
            The stations data for the given region as a GeoDataFrame.

        """
        stations_df = self._get_stations_df()
        stations_gdf = gpd.GeoDataFrame(
            stations_df,
            geometry=gpd.points_from_xy(
                stations_df[self.X_COL], stations_df[self.Y_COL]
            ),
            crs=self.CRS,
        )
        # filter the stations
        # TODO: do we need to copy the dict to avoid reference issues?
        _sjoin_kwargs = self.SJOIN_KWARGS.copy()
        # predicate = _sjoin_kws.pop("predicate", SJOIN_PREDICATE)
        return stations_gdf.sjoin(self.region[["geometry"]], **_sjoin_kwargs)[
            stations_gdf.columns
        ]

    @property
    def stations_gdf(self) -> gpd.GeoDataFrame:
        """Geo-data frame with stations data."""
        try:
            return self._stations_gdf
        except AttributeError:
            # rename here because some clients may override `_get_stations_gdf`
            self._stations_gdf = (
                self._get_stations_gdf()
                .rename(columns={self._stations_gdf_id_col: settings.STATIONS_ID_COL})
                .set_index(settings.STATIONS_ID_COL)
            )
            return self._stations_gdf

    # time series data
    @utils.abstract_attribute
    def _ts_endpoint(self) -> str:
        pass

    def _ts_params(self, variable_ids, *args, **kwargs) -> dict:
        return {"variable_ids": variable_ids, **kwargs}

    def _post_process_ts_df(self, ts_df: pd.DataFrame) -> pd.DataFrame:
        return ts_df.apply(pd.to_numeric, axis="columns")  # .sort_index()

    def _rename_variables_cols(
        self, ts_df: pd.DataFrame, variable_id_ser: pd.Series
    ) -> pd.DataFrame:
        # TODO: avoid this if the user provided variable codes (in which case the dict
        # maps variable codes to variable codes)?
        # also keep only columns of requested variables
        return ts_df[variable_id_ser].rename(
            columns={
                variable_id: variable
                for variable, variable_id in variable_id_ser.items()
            }
        )

    def _coerce_variable_id(self, variable_id):
        """Coerce a variable id to match the variables dataframe dtype."""
        try:
            variables_df = self.variables_df
            dtype = variables_df[self._variables_id_col].dtype
        except Exception:
            return variable_id
        try:
            return pd.Series([variable_id], dtype=dtype).iloc[0]
        except Exception:
            return variable_id

    def _units_by_id(self) -> dict | None:
        """Return a mapping of variable ids to units, if defined."""
        units_map = getattr(self, "_variable_units_dict", None)
        if units_map is None:
            return None
        return {
            self._coerce_variable_id(variable_id): unit
            for variable_id, unit in units_map.items()
        }

    def _ecv_by_variable_id(self) -> dict:
        """Return a mapping of variable ids to ECV names."""
        return {
            self._coerce_variable_id(variable_id): ecv
            for ecv, variable_id in self._ecv_dict.items()
        }

    def _get_units_map(self, variable_id_ser: pd.Series) -> dict:
        """Return a mapping of requested variables to their units."""
        units_by_id = self._units_by_id()
        ecv_by_id = self._ecv_by_variable_id()

        units_map = {}
        for variable, variable_id in variable_id_ser.items():
            if units_by_id is not None:
                unit = units_by_id.get(variable_id)
                if unit is None and isinstance(variable, str):
                    unit = units_by_id.get(variable)
            else:
                if isinstance(variable, str) and variable in settings.ECV_UNIT_DICT:
                    unit = settings.ECV_UNIT_DICT[variable]
                else:
                    ecv = ecv_by_id.get(variable_id)
                    unit = None if ecv is None else settings.ECV_UNIT_DICT.get(ecv)
            if unit is None:
                raise ValueError(f"Missing unit for variable {variable!r}.")
            units_map[variable] = unit

        return units_map

    @abc.abstractmethod
    def _ts_df_from_endpoint(self, ts_params: Mapping) -> pd.DataFrame:
        pass

    def _get_ts_df(self, variables: VariablesType, *args, **kwargs) -> pd.DataFrame:
        # process the variables arg
        variable_id_ser = self._get_variable_id_ser(variables)

        # prepare base request parameters
        ts_params = self._ts_params(variable_id_ser, *args, **kwargs)

        # perform request
        ts_df = self._ts_df_from_endpoint(ts_params)

        # ACHTUNG: do NOT set the station, time multi-index here because this is already
        # done in `_ts_df_from_content` in many cases since it results from groupby,
        # stack or pivot operations
        # # set station, time multi-index
        # ts_df = ts_df.set_index([self._stations_id_col, self._time_col])

        # ensure that we return the variable column names as provided by the user in the
        # `variables` argument (e.g., if the user provided variable codes, use
        # variable codes in the column names).
        ts_df = self._rename_variables_cols(ts_df, variable_id_ser)

        # apply a generic post-processing function (by default, ensuring numeric dtypes
        # and sorting)
        ts_df = self._post_process_ts_df(ts_df)

        # rename stations and id labels in multi-level index
        ts_df = ts_df.rename_axis(
            index={
                self._ts_df_stations_id_col: settings.STATIONS_ID_COL,
                self._ts_df_time_col: settings.TIME_COL,
            }
        )

        # attach units
        units_map = self._get_units_map(variable_id_ser)
        ts_df = units.attach_units(ts_df, units_map)

        # return
        return ts_df


class BaseRequestClient(BaseClient, abc.ABC):
    """Base class for clients that request content over HTTP."""

    def _get(
        self,
        url: str,
        *,
        params: KwargsType = None,
        headers: KwargsType = None,
        **request_kwargs: KwargsType,
    ) -> requests.Response:
        """Get response for the url (from the cache or from the API).

        Parameters
        ----------
        url : str
            URL to request.
        params : dict, optional
            Parameters to pass to the request. They will be added to the default params
            set in the `request_params` property.
        headers : dict, optional
            Headers to pass to the request. They will be added to the default headers
            set in the `request_headers` property.
        request_kwargs : dict, optional
            Additional keyword arguments to pass to `requests.get`. If None, the value
            from `settings.REQUEST_KWARGS` is used.

        Returns
        -------
        response : requests.Response
            Response object from the server.
        """
        _params = self.request_params.copy()
        _headers = self.request_headers.copy()
        _request_kwargs = settings.REQUEST_KWARGS.copy()
        if params is not None:
            _params.update(params)
        if headers is not None:
            _headers.update(headers)
        if request_kwargs is not None:
            _request_kwargs.update(request_kwargs)

        return self._session.get(
            url, params=_params, headers=_headers, **_request_kwargs
        )

    @abc.abstractmethod
    def _get_content_from_response(self, response: requests.Response):
        pass

    def _get_content_from_url(
        self,
        url: str,
        params: KwargsType = None,
        headers: KwargsType = None,
        request_kwargs: KwargsType = None,
        pause: int | None = None,
        error_pause: int | None = None,
    ):
        """Get the response content from a given URL.

        Parameters
        ----------
        url : str
            URL to request.
        params : dict, optional
            Parameters to pass to the request. They will be added to the default params
            set in the `request_params` property.
        headers : dict, optional
            Headers to pass to the request. They will be added to the default headers
            set in the `request_headers` property.
        request_kwargs : dict, optional
            Additional keyword arguments to pass to `requests.get`. If None, the value
            from `settings.REQUEST_KWARGS` is used.
        pause : int, optional
            How long to pause before request, in seconds. If None, the value from
            `settings.PAUSE` is used.
        error_pause : int, optional
            How long to pause in seconds before re-trying request if error. If None, the
            value from `settings.ERROR_PAUSE` is used.

        Returns
        -------
        response_content
            Response content.
        """
        if request_kwargs is None:
            request_kwargs = {}
        response = self._get(url, params=params, headers=headers, **request_kwargs)
        sc = response.status_code
        try:
            response_content = self._get_content_from_response(response)
        except Exception:  # pragma: no cover
            domain = re.findall(r"(?s)//(.*?)/", url)[0]
            if sc in {429, 504}:
                # 429 is 'too many requests' and 504 is 'gateway timeout' from
                # server overload: handle these by pausing then recursively
                # re-trying until we get a valid response from the server
                if error_pause is None:
                    error_pause = settings.ERROR_PAUSE
                utils.log(
                    f"{domain} returned {sc}: retry in {error_pause} secs",
                    level=lg.WARNING,
                )
                time.sleep(error_pause)
                # note that this is a recursive call
                response_content = self._get_content_from_url(
                    url,
                    params=params,
                    headers=headers,
                    request_kwargs=request_kwargs,
                    pause=pause,
                    error_pause=error_pause,
                )
            else:
                # else, this was an unhandled status code, throw an exception
                utils.log(f"{domain} returned {sc}", level=lg.ERROR)
                raise Exception(
                    f"Server returned:\n{response} {response.reason}\n{response.text}"
                )

        return response_content

    def _stations_df_from_endpoint(self) -> pd.DataFrame:
        response_content = self._get_content_from_url(self._stations_endpoint)
        return self._stations_df_from_content(response_content)

    def _variables_df_from_endpoint(self) -> pd.DataFrame:
        response_content = self._get_content_from_url(self._variables_endpoint)
        return self._variables_df_from_content(response_content)

    def _ts_df_from_endpoint(self, ts_params: Mapping) -> pd.DataFrame:
        # perform request
        response_content = self._get_content_from_url(
            self._ts_endpoint, params=ts_params
        )

        # process response content into a time series data frame
        return self._ts_df_from_content(response_content)


class BaseJSONClient(BaseRequestClient):
    """Base class for clients that return JSON-encoded responses."""

    def _get_content_from_response(self, response: requests.Response) -> dict:
        return response.json()


class BaseTextClient(BaseRequestClient):
    """Base class for clients that return text-encoded (e.g., CSV) responses."""

    def _get_content_from_response(
        self,
        response: requests.Response,
    ) -> io.StringIO:
        return io.StringIO(response.content.decode(response.encoding))


class BaseFileClient(BaseClient):
    """Base class for clients that operate on file URLs (e.g., CSV)."""

    @property
    def pooch_kwargs(self) -> dict:
        """Keyword arguments to pass to pooch retrieval calls."""
        try:
            return self._pooch_kwargs
        except AttributeError:
            self._pooch_kwargs = {}
            return self._pooch_kwargs

    @pooch_kwargs.setter
    def pooch_kwargs(self, value: dict | None) -> None:
        self._pooch_kwargs = {} if value is None else value

    def _retrieve_file(
        self,
        url: str,
        *,
        known_hash: str | None = None,
        cache: bool = True,
        pooch_kwargs: KwargsType | None = None,
    ) -> str | io.BytesIO:
        if cache:
            _pooch_kwargs = self.pooch_kwargs.copy()
            if pooch_kwargs is not None:
                _pooch_kwargs.update(pooch_kwargs)
            try:
                return pooch.retrieve(url, known_hash, **_pooch_kwargs)
            except ValueError:
                if known_hash is None:
                    raise
                utils.log(
                    f"Pooch hash mismatch for '{url}', accepting updated download.",
                    level=lg.WARNING,
                )
                return pooch.retrieve(url, None, **_pooch_kwargs)

        response = requests.get(
            url,
            params=self.request_params,
            headers=self.request_headers,
            **settings.REQUEST_KWARGS,
        )
        response.raise_for_status()
        return io.BytesIO(response.content)

    def _read_csv_from_url(
        self,
        url: str,
        *,
        known_hash: str | None = None,
        cache: bool = True,
        read_csv_kwargs: KwargsType | None = None,
    ) -> pd.DataFrame:
        if read_csv_kwargs is None:
            read_csv_kwargs = {}
        source = self._retrieve_file(url, known_hash=known_hash, cache=cache)
        return pd.read_csv(source, **read_csv_kwargs)

    def _stations_cache_policy(self) -> tuple[bool, str | None]:
        known_hash = getattr(self, "_stations_known_hash", None)
        cache = getattr(self, "_stations_cache", None)
        if cache is None:
            cache = known_hash is not None
        return cache, known_hash

    def _variables_cache_policy(self) -> tuple[bool, str | None]:
        known_hash = getattr(self, "_variables_known_hash", None)
        cache = getattr(self, "_variables_cache", None)
        if cache is None:
            cache = known_hash is not None
        return cache, known_hash

    def _stations_df_from_endpoint(self) -> pd.DataFrame:
        cache, known_hash = self._stations_cache_policy()
        read_csv_kwargs = getattr(self, "_stations_read_csv_kwargs", {})
        return self._read_csv_from_url(
            self._stations_endpoint,
            known_hash=known_hash,
            cache=cache,
            read_csv_kwargs=read_csv_kwargs,
        )

    def _variables_df_from_endpoint(self) -> pd.DataFrame:
        cache, known_hash = self._variables_cache_policy()
        read_csv_kwargs = getattr(self, "_variables_read_csv_kwargs", {})
        return self._read_csv_from_url(
            self._variables_endpoint,
            known_hash=known_hash,
            cache=cache,
            read_csv_kwargs=read_csv_kwargs,
        )

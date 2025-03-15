"""Base abstract classes for meteo station datasets."""

import abc
import datetime
import io
import logging as lg
import os
import re
import time
from collections.abc import Mapping, Sequence
from typing import IO

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import requests
import requests_cache
from pyogrio.errors import DataSourceError
from pyproj.crs import CRS
from shapely import geometry
from shapely.geometry.base import BaseGeometry

from meteora import settings, utils

try:
    import osmnx as ox
except ImportError:
    ox = None


__all__ = [
    "BaseJSONClient",
    "BaseTextClient",
    "RegionType",
    "VariablesType",
    "DateTimeType",
    "CRSType",
    "KwargsType",
]


# def _long_ts_df(ts_df, station_id_name, time_name, value_name):
#     """Transform time series data frame from wide (default) to long format."""
#     return pd.melt(
#         ts_df.reset_index(),
#         id_vars=time_name,
#         var_name=station_id_name,
#         value_name=value_name,
#     )

RegionType = str | Sequence | gpd.GeoSeries | gpd.GeoDataFrame | os.PathLike | IO
VariablesType = str | int | list[str] | list[int]
DateTimeType = (
    datetime.date | datetime.datetime | np.datetime64 | pd.Timestamp | str | int | float
)
CRSType = str | dict | CRS
KwargsType = Mapping | None


class BaseClient(abc.ABC):
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

    @property
    def region(self) -> gpd.GeoDataFrame | None:
        """The region as a GeoDataFrame."""
        return self._region

    @region.setter
    def region(
        self,
        region: RegionType,
    ):
        self._region = self._process_region_arg(region)

    def _process_region_arg(
        self,
        region: RegionType,
        **geocode_to_gdf_kwargs: KwargsType,
    ) -> gpd.GeoDataFrame | None:
        """Process the region argument.

        Parameters
        ----------
        region : str, Sequence, GeoSeries, GeoDataFrame, PathLike, or IO
            The region to process. This can be either:
            -  A string with a place name (Nominatim query) to geocode.
            -  A sequence with the west, south, east and north bounds.
            -  A geometric object, e.g., shapely geometry, or a sequence of geometric
               objects. In such a case, the value is passed as the `data` argument of
               the GeoSeries constructor, and needs to be in the same CRS as the one
               used by the client's class (i.e., the `CRS` class attribute).
            -  A geopandas geo-series or geo-data frame.
            -  A filename or URL, a file-like object opened in binary ('rb') mode, or a
               Path object that will be passed to `geopandas.read_file`.
        geocode_to_gdf_kwargs : dict, optional
            Keyword arguments to pass to `geocode_to_gdf` if `region` is a string
            corresponding to a place name (Nominatim query).

        Returns
        -------
        gdf : GeoDataFrame
            The processed region as a GeoDataFrame, in the CRS used by the client's
            class. A value of None is returned when passing a place name (Nominatim
            query) but osmnx is not installed.
        """
        # crs : Any, optional
        # Coordinate Reference System of the provided `region`. Ignored if `region` is a
        # string corresponding to a place name, a geopandas geo-series or geo-data frame
        # with its CRS attribute set or a filename, URL or file-like object. Can be
        # anything accepted by `pyproj.CRS.from_user_input()`, such as an authority
        # string (eg “EPSG:4326”) or a WKT string.

        if not isinstance(region, gpd.GeoDataFrame):
            # naive geometries
            if not isinstance(region, gpd.GeoSeries) and (
                hasattr(region, "__iter__")
                and not isinstance(region, str)
                or isinstance(region, BaseGeometry)
            ):
                # if region is a sequence (other than a string)
                # use the hasattr to avoid AttributeError when region is a BaseGeometry
                if hasattr(region, "__len__"):
                    if len(region) == 4 and isinstance(region[0], (int, float)):
                        # if region is a sequence of 4 numbers, assume it's a bounding
                        # box
                        region = geometry.box(*region)
                # otherwise, assume it's a geometry or sequence of geometries that can
                # be passed as the `data` argument of the GeoSeries constructor
                region = gpd.GeoSeries(region, crs=self.CRS)
            if isinstance(region, gpd.GeoSeries):
                # if we have a GeoSeries, convert it to a GeoDataFrame so that we can
                # use the same code
                region = gpd.GeoDataFrame(
                    geometry=region, crs=getattr(region, "crs", self.CRS)
                )
            else:
                # at this point, we assume that this is either file-like or a Nominatim
                # query
                try:
                    region = gpd.read_file(region)
                except (DataSourceError, AttributeError):
                    #             if ox is None:
                    #                 lg.warning(
                    #                     """
                    # Using a Nominatim query as `region` argument requires osmnx.
                    # You can install it using conda or pip.
                    # """
                    #                 )
                    #                 return

                    if geocode_to_gdf_kwargs is None:
                        geocode_to_gdf_kwargs = {}
                    region = ox.geocode_to_gdf(region, **geocode_to_gdf_kwargs).iloc[:1]

        return region.to_crs(self.CRS)

    @property
    def request_headers(self) -> dict:
        """Request headers."""
        return {}

    @property
    def request_params(self) -> dict:
        """Request parameters."""
        return {}

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

    @utils.abstract_attribute
    def _ts_endpoint(self) -> str:
        pass

    def _ts_params(self, variable_ids, *args, **kwargs) -> dict:
        return {}

    def _post_process_ts_df(self, ts_df: pd.DataFrame) -> pd.DataFrame:
        return ts_df.apply(pd.to_numeric, axis="columns").sort_index()

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

    def _ts_df_from_endpoint(self, ts_params: Mapping) -> pd.DataFrame:
        # perform request
        response_content = self._get_content_from_url(
            self._ts_endpoint, params=ts_params
        )

        # process response content into a time series data frame
        return self._ts_df_from_content(response_content)

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

        # apply a generic post-processing function
        return self._post_process_ts_df(ts_df)


class BaseJSONClient(BaseClient):
    """Base class for JSON clients."""

    def _get_content_from_response(self, response: requests.Response) -> dict:
        return response.json()


class BaseTextClient(BaseClient):
    """Base class for text clients."""

    def _get_content_from_response(
        self,
        response: requests.Response,
    ) -> io.StringIO:
        return io.StringIO(response.content.decode(response.encoding))

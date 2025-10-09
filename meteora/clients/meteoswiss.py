"""MeteoSwiss client."""

import datetime as dt
from collections.abc import Iterable, Mapping

import pandas as pd
import pyproj

from meteora import settings
from meteora.clients.base import BaseTextClient
from meteora.mixins import (
    MultiRequestTSMixin,
    StationsEndpointMixin,
    VariablesEndpointMixin,
)
from meteora.utils import CRSType, DateTimeType, KwargsType, RegionType, VariablesType

BASE_URL = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn"
STATIONS_ENDPOINT = f"{BASE_URL}/ogd-smn_meta_stations.csv"
VARIABLES_ENDPOINT = f"{BASE_URL}/ogd-smn_meta_parameters.csv"
# there are several ways to structure a time series request, for more details see
# https://opendatadocs.meteoswiss.ch/general/download#how-csv-files-are-structured
# - the `t` corresponds to the "original data" (Originalwert), i.e., the 10min value,
#   all the other granularities are aggregations (e.g., `h` for hourly...)
# - the `{update_freq}` part can be either `historical` (until Dec 31st of last year) or
#   `recent` (from Jan 1st of this year until yesterday).
# Additionally, for `historical` data, an additional part of the form `_{decade}` must
# be added to the URL, e.g., `_1980-1989` for the 1980s decade.
TS_ENDPOINT = f"{BASE_URL}/" + "{station_id}/ogd-smn_{station_id}_t_{update_freq}.csv"

# useful constants
# TODO: DRY with Agrometeo?
LONLAT_CRS = pyproj.CRS("epsg:4326")
LV95_CRS = pyproj.CRS("epsg:2056")
# ACHTUNG: for some reason, the API mixes up the longitude and latitude columns ONLY in
# the CH1903/LV03 projection. This is why we need to swap the columns in the dict below.
GEOM_COL_DICT = {
    LONLAT_CRS: ["station_coordinates_wgs84_lat", "station_coordinates_wgs84_lon"],
    LV95_CRS: ["station_coordinates_lv95_east", "station_coordinates_lv95_north"],
}
DEFAULT_CRS = LV95_CRS
READ_CSV_KWARGS = dict(sep=";", encoding="ISO-8859-1")
# stations column used by the MeteoSwiss API (do not change)
STATIONS_GDF_ID_COL = "station_abbr"
TS_DF_STATIONS_ID_COL = "station_abbr"
TS_DF_TIME_COL = "reference_timestamp"
VARIABLES_ID_COL = "parameter_shortname"
ECV_DICT = {
    # precipitation
    # "Precipitation (ten minutes total) [mm]"
    "precipitation": "rre150z0",
    # pressure
    # "Atmospheric pressure at barometric altitude (current value) [hPa]"
    "pressure": "prestas0",
    # radiation budget
    # "Global radiation (ten minutes mean) [W/m2]"
    "radiation_shortwave": "gre000z0",
    # "Longwave incoming radiation; ten minute mean [W/m2]"
    "radiation_longwave_incoming": "oli000z0",
    # "Longwave outgoing radiation; ten minute mean [W/m2]"
    "radiation_longwave_outgoing": "olo000z0",
    # temperature
    # "Air temperature 2 m above ground (current value) [°C]"
    "temperature": "tre200s0",
    # water vapour
    # "Dew point 2 m above ground [°C]"
    "dew_point": "tde200h0",
    # "Relative air humidity 2 m above ground (current value) [%]"
    "relative_humidity": "ure200s0",
    # wind
    # "Wind speed scalar (ten minutes mean) [m/s]",
    "wind_speed": "fkl010z0",
    # "Wind direction (ten minutes mean) [degrees]",
    "wind_direction": "dkl010z0",
}


class MeteoSwissClient(StationsEndpointMixin, VariablesEndpointMixin, BaseTextClient):
    """MeteoSwiss client.

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
    crs : str, dict or pyproj.CRS, optional
        The coordinate reference system (CRS) to be used. For Agrometeo, the
        provided value must be equivalent to either the EPSG:21781 (default) or
        EPSG:4326.
    sjoin_kwargs : dict, optional
        Keyword arguments to pass to the `geopandas.sjoin` function when filtering the
        stations within the region. If None, the value from `settings.SJOIN_KWARGS` is
        used.
    """

    # API endpoints
    _stations_endpoint = STATIONS_ENDPOINT
    _variables_endpoint = VARIABLES_ENDPOINT
    _ts_endpoint = TS_ENDPOINT

    # data frame labels constants
    _stations_gdf_id_col = STATIONS_GDF_ID_COL
    _ts_df_stations_id_col = TS_DF_STATIONS_ID_COL
    _ts_df_time_col = TS_DF_TIME_COL
    _variables_id_col = VARIABLES_ID_COL
    _ecv_dict = ECV_DICT

    def __init__(
        self,
        region: RegionType,
        *,
        crs: CRSType | None = None,
        **sjoin_kwargs: KwargsType,
    ) -> None:
        """Initialize MeteoSwiss client."""
        # TODO: DRY with Agrometeo?
        if crs is not None:
            crs = pyproj.CRS(crs)
        else:
            crs = DEFAULT_CRS
        self.CRS = crs
        # self._variables_name_col = variables_name_col or VARIABLES_NAME_COL
        try:
            self.X_COL, self.Y_COL = GEOM_COL_DICT[self.CRS]
        except KeyError:
            raise ValueError(
                f"CRS must be among {list(GEOM_COL_DICT.keys())}, got {self.CRS}"
            )

        self.region = region
        if sjoin_kwargs is None:
            sjoin_kwargs = settings.SJOIN_KWARGS.copy()
        self.SJOIN_KWARGS = sjoin_kwargs

        # need to call super().__init__() to set the cache
        super().__init__()

    def _stations_df_from_content(self, response_content) -> pd.DataFrame:
        # return pd.read_csv(self._stations_endpoint, encoding=FILE_ENCODING)
        return pd.read_csv(response_content, **READ_CSV_KWARGS)

    def _variables_df_from_content(self, response_content) -> pd.DataFrame:
        return pd.read_csv(response_content, **READ_CSV_KWARGS)

    def _ts_df_from_content(self, response_content) -> pd.DataFrame:
        return pd.read_csv(response_content, **READ_CSV_KWARGS)

    def _ts_df_from_endpoint(self, ts_params: Mapping) -> pd.DataFrame:
        # the API only allows returning data for a given station so we have to iterate
        # over the list of stations
        # determine whether we need to access the "historical" or "recent" URL, see
        # https://opendatadocs.meteoswiss.ch/general/download#update-frequency
        this_year_start = dt.date(dt.datetime.now().year, 1, 1)

        # TODO: better approach to ensure datetime types in `ts_params`
        start = pd.Timestamp(ts_params["start"])
        end = pd.Timestamp(ts_params["end"])
        if start.date() > this_year_start:
            # the first requested data is after the start of the current year, so we
            # only need to query the data from the "recent" file
            def _get_station_urls(station_id):
                return [
                    self._ts_endpoint.format(
                        station_id=station_id,
                        update_freq="recent",
                    )
                ]
        else:
            # we need to query the data from at least one "historical" file (there is a
            # "historical" file for each decade, e.g., 1980-1989, 1990-1999, etc.)
            decades = []
            for year in range((start.year // 10) * 10, (end.year // 10) * 10 + 1, 10):
                decades.append(f"{year}-{year + 9}")

            def _get_station_decades_urls(station_id):
                return [
                    self._ts_endpoint.format(
                        station_id=station_id,
                        update_freq=f"historical_{decade}",
                    )
                    for decade in decades
                ]

            if end.date() < this_year_start:
                # the last requested data is before the start of the current year, so we
                # only need to query the data from the "historical" file of each decade
                def _get_station_urls(station_id):
                    return _get_station_decades_urls(station_id)
            else:
                # assume that we need to query both the "historical" and "recent" files
                def _get_station_urls(station_id):
                    return _get_station_decades_urls(station_id) + [
                        self._ts_endpoint.format(
                            station_id=station_id,
                            update_freq="recent",
                        )
                    ]

        def _ts_df_from_url(station_url):
            # read file into a pandas data frame
            ts_df = self._ts_df_from_content(self._get_content_from_url(station_url))
            # set time and station id columns as index
            ts_df = ts_df.assign(
                **{
                    self._ts_df_time_col: pd.to_datetime(
                        ts_df[self._ts_df_time_col], format="%d.%m.%Y %H:%M"
                    )
                }
            ).set_index([self._ts_df_stations_id_col, self._ts_df_time_col])
            # filter time range
            # TODO: dry with Agrometeo and Meteocat
            time_ser = ts_df.index.get_level_values(self._ts_df_time_col).to_series()
            tz = time_ser.dt.tz
            return ts_df.loc[
                (
                    slice(None),
                    time_ser.between(
                        pd.Timestamp(start, tz=tz),
                        pd.Timestamp(end, tz=tz),
                        inclusive="both",
                    ),
                ),
                :,
            ]

        return pd.concat(
            [
                _ts_df_from_url(station_url)
                for station_id in self.stations_gdf.index.str.lower()
                for station_url in _get_station_urls(station_id)
            ],
            axis="index",
        )

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
            Target variables, which can be either an Agrometeo variable code (integer or
            string) or an essential climate variable (ECV) following the Meteora
            nomenclature (string).
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
        return self._get_ts_df(
            variables=variables,
            start=start,
            end=end,
        )


class _MeteoSwissClient(MultiRequestTSMixin, MeteoSwissClient):
    def _get_ts_request_list(self, ts_params: Mapping) -> Iterable:
        # the API only allows returning data for a given station so we have to iterate
        # over the list of stations
        # determine whether we need to access the "historical" or "recent" URL, see
        # https://opendatadocs.meteoswiss.ch/general/download#update-frequency
        this_year_start = dt.date(dt.datetime.now().year, 1, 1)

        # TODO: better approach to ensure datetime types in `ts_params`
        start = pd.Timestamp(ts_params["start"])
        if start.date() > this_year_start:
            # the first requested data is after the start of the current year, so we
            # only need to query the data from the "recent" file
            def _get_station_urls(station_id):
                return [
                    self._ts_endpoint.format(
                        station_id=station_id,
                        update_freq="recent",
                    )
                ]
        else:
            # TODO: better approach to ensure datetime types in `ts_params`
            end = pd.Timestamp(ts_params["end"])
            # we need to query the data from at least one "historical" file (there is a
            # "historical" file for each decade, e.g., 1980-1989, 1990-1999, etc.)
            decades = []
            for year in range((start.year // 10) * 10, (end.year // 10) * 10 + 1, 10):
                decades.append(f"{year}-{year + 9}")

            def _get_station_decades_urls(station_id):
                return [
                    self._ts_endpoint.format(
                        station_id=station_id,
                        update_freq=f"historical_{decade}",
                    )
                    for decade in decades
                ]

            if end.date() < this_year_start:
                # the last requested data is before the start of the current year, so we
                # only need to query the data from the "historical" file of each decade
                def _get_station_urls(station_id):
                    return _get_station_decades_urls(station_id)
            else:
                # assume that we need to query both the "historical" and "recent" files
                def _get_station_urls(station_id):
                    return _get_station_decades_urls(station_id) + [
                        self._ts_endpoint.format(
                            station_id=station_id,
                            update_freq="recent",
                        )
                    ]

            return [
                station_url
                for station_id in self.stations_gdf.index.str.lower()
                for station_url in _get_station_urls(station_id)
            ]

        def _request_to_ts_df(self, station_url: str) -> pd.DataFrame:
            # read file into a pandas data frame
            ts_df = self._ts_df_from_content(self._get_content_from_url(station_url))
            # set time and station id columns as index
            ts_df = ts_df.assign(
                **{
                    self._ts_df_time_col: pd.to_datetime(
                        ts_df[self._ts_df_time_col], format="%d.%m.%Y %H:%M"
                    )
                }
            ).set_index([self._ts_df_stations_id_col, self._ts_df_time_col])
            # filter time range
            # TODO: dry with Agrometeo and Meteocat
            time_ser = ts_df.index.get_level_values(self._ts_df_time_col).to_series()
            tz = time_ser.dt.tz
            return ts_df.loc[
                (
                    slice(None),
                    time_ser.between(
                        pd.Timestamp(start, tz=tz),
                        pd.Timestamp(end, tz=tz),
                        inclusive="both",
                    ),
                ),
                :,
            ]

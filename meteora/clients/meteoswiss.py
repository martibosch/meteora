"""MeteoSwiss client."""

import datetime as dt
import os
from collections.abc import Mapping

import pandas as pd
import pyproj
from pyregeon import CRSType, RegionType

from meteora import settings, utils
from meteora.clients.base import BaseFileClient
from meteora.clients.mixins import (
    StationPartitionedTSMixin,
    StationsEndpointMixin,
    TimePartitionedTSMixin,
    VariablesEndpointMixin,
)
from meteora.utils import DateTimeType, KwargsType, VariablesType

BASE_URL = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn"
STATIONS_ENDPOINT = f"{BASE_URL}/ogd-smn_meta_stations.csv"
VARIABLES_ENDPOINT = f"{BASE_URL}/ogd-smn_meta_parameters.csv"
# there are several ways to structure a time series request, for more details see
# https://opendatadocs.meteoswiss.ch/general/download#how-csv-files-are-structured
# - the `t` corresponds to the "original data" (Originalwert), i.e., the 10min value,
#   all the other granularities are aggregations (e.g., `h` for hourly...)
# - the `{period}` part can be either `historical_YYYY-YYYY` (until Dec 31st of last
#   year) or `recent` (from Jan 1st of this year until yesterday).
TS_ENDPOINT = f"{BASE_URL}/" + "{station_id}/ogd-smn_{station_id}_t_{period}.csv"

# useful constants
# TODO: DRY with Agrometeo?
LONLAT_CRS = utils.LONLAT_CRS
LV95_CRS = pyproj.CRS("epsg:2056")
# ACHTUNG: for some reason, the API mixes up the longitude and latitude columns ONLY in
# the CH1903/LV03 projection. This is why we need to swap the columns in the dict below.
GEOM_COL_DICT = {
    LONLAT_CRS: ["station_coordinates_wgs84_lon", "station_coordinates_wgs84_lat"],
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
    settings.ECV_PRECIPITATION: "rre150z0",
    # pressure
    # "Atmospheric pressure at barometric altitude (current value) [hPa]"
    settings.ECV_PRESSURE: "prestas0",
    # radiation budget
    # "Global radiation (ten minutes mean) [W/m2]"
    settings.ECV_RADIATION_SHORTWAVE: "gre000z0",
    # "Longwave incoming radiation; ten minute mean [W/m2]"
    settings.ECV_RADIATION_LONGWAVE_INCOMING: "oli000z0",
    # "Longwave outgoing radiation; ten minute mean [W/m2]"
    settings.ECV_RADIATION_LONGWAVE_OUTGOING: "olo000z0",
    # temperature
    # "Air temperature 2 m above ground (current value) [°C]"
    settings.ECV_TEMPERATURE: "tre200s0",
    # water vapour
    # "Dew point 2 m above ground [°C]"
    settings.ECV_DEW_POINT_TEMPERATURE: "tde200h0",
    # "Relative air humidity 2 m above ground (current value) [%]"
    settings.ECV_RELATIVE_HUMIDITY: "ure200s0",
    # wind
    # "Wind speed scalar (ten minutes mean) [m/s]",
    settings.ECV_WIND_SPEED: "fkl010z0",
    # "Wind direction (ten minutes mean) [degrees]",
    settings.ECV_WIND_DIRECTION: "dkl010z0",
}


class MeteoSwissClient(
    StationPartitionedTSMixin,
    TimePartitionedTSMixin,
    StationsEndpointMixin,
    VariablesEndpointMixin,
    BaseFileClient,
):
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
    pooch_kwargs : dict, optional
        Keyword arguments to pass to the `pooch.retrieve` function when caching file
        downloads.
    sjoin_kwargs : dict, optional
        Keyword arguments to pass to the `geopandas.sjoin` function when filtering the
        stations within the region. If None, the value from `settings.SJOIN_KWARGS` is
        used.
    """

    # API endpoints
    _stations_endpoint = STATIONS_ENDPOINT
    _variables_endpoint = VARIABLES_ENDPOINT
    _ts_endpoint = TS_ENDPOINT
    _stations_read_csv_kwargs = READ_CSV_KWARGS
    _variables_read_csv_kwargs = READ_CSV_KWARGS

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
        pooch_kwargs: KwargsType | None = None,
        **sjoin_kwargs: KwargsType,
    ) -> None:
        """Initialize MeteoSwiss client."""
        # TODO: DRY with Agrometeo?
        if crs is not None:
            crs = pyproj.CRS(crs)
        else:
            crs = DEFAULT_CRS
        self.CRS = crs
        try:
            self.X_COL, self.Y_COL = GEOM_COL_DICT[self.CRS]
        except KeyError:
            raise ValueError(
                f"CRS must be among {list(GEOM_COL_DICT.keys())}, got {self.CRS}"
            )

        self.region = region
        if not sjoin_kwargs:
            sjoin_kwargs = settings.SJOIN_KWARGS.copy()
        self.SJOIN_KWARGS = sjoin_kwargs
        if pooch_kwargs is None:
            pooch_kwargs = {}
        self.pooch_kwargs = pooch_kwargs

        # need to call super().__init__() to set the cache
        super().__init__()

    def _iter_time_partitions(self, ts_params: Mapping):
        # determine whether we need "historical" or "recent" files, see
        # https://opendatadocs.meteoswiss.ch/general/download#update-frequency
        this_year_start = dt.date(dt.datetime.now().year, 1, 1)
        start = pd.Timestamp(ts_params["start"])
        end = pd.Timestamp(ts_params["end"])

        if start.date() >= this_year_start:
            return [{"period": "recent"}]

        decades = [
            f"{year}-{year + 9}"
            for year in range((start.year // 10) * 10, (end.year // 10) * 10 + 1, 10)
        ]
        update_freqs = [f"historical_{decade}" for decade in decades]
        if end.date() >= this_year_start:
            update_freqs.append("recent")
        return [{"period": uf} for uf in update_freqs]

    def _format_ts_endpoint(self, ts_params: Mapping) -> str:
        # MeteoSwiss station IDs in URLs are lowercase
        return self._ts_endpoint.format(
            **{**ts_params, "station_id": ts_params["station_id"].lower()}
        )

    def _ts_cache(self, ts_params: Mapping) -> bool:
        period = ts_params["period"]
        if period == "recent":
            return False
        # for historical, always cache unless we're in December and the period
        # includes the current year (the file may still be getting populated)
        today = dt.date.today()
        if today.month != 12:
            return True
        decade = period.split("historical_", 1)[1]
        start_year, end_year = (int(y) for y in decade.split("-"))
        return not (start_year <= today.year <= end_year)

    def _ts_df_from_url(self, url, ts_params: Mapping) -> pd.DataFrame:
        start = pd.Timestamp(ts_params["start"])
        end = pd.Timestamp(ts_params["end"])
        period = ts_params["period"]
        _station_id = ts_params["station_id"].lower()

        def _parse(source):
            ts_df = pd.read_csv(source, **READ_CSV_KWARGS)
            ts_df = ts_df.assign(
                **{
                    self._ts_df_time_col: pd.to_datetime(
                        ts_df[self._ts_df_time_col], format="%d.%m.%Y %H:%M"
                    )
                }
            ).set_index([self._ts_df_stations_id_col, self._ts_df_time_col])
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

        ts_source = self._ts_source(url, ts_params)
        ts_df = _parse(ts_source)

        if ts_df.empty and period.startswith("historical_"):
            utils.log(
                f"The requested data for the given period and station "
                f"'{_station_id}' returned an empty data frame. This can happen "
                "when requesting data from the past year during the first "
                "months of the year, since 'historical' data for the "
                "corresponding decade has not been updated with the data from "
                "the previous year yet. In this case, we will try to retrieve "
                "the 'recent' data instead.",
            )
            current_periods = [
                p["period"] for p in self._iter_time_partitions(ts_params)
            ]
            if "recent" not in current_periods:
                recent_url = self._format_ts_endpoint({**ts_params, "period": "recent"})
                recent_source = self._retrieve_file(recent_url, cache=False)
                ts_df = _parse(recent_source)
                if ts_df.empty:
                    utils.log(
                        f"The requested data for the given period and station "
                        f"'{_station_id}' is not on the 'recent' data either. "
                        "This can happen when the 'historical' data for the "
                        "corresponding decade is cached locally but has been "
                        "already updated in the MeteoSwiss API. Accordingly, we"
                        " will try to update the 'historical' file and retrieve"
                        " the requested data from the updated file.",
                    )
                    os.remove(ts_source)
                    utils.log(
                        f"Removed cached file '{ts_source}' for station "
                        f"'{_station_id}' to force the retrieval of the updated "
                        f"'historical' data from the MeteoSwiss API."
                    )
                    ts_source = self._ts_source(url, ts_params)
                    ts_df = _parse(ts_source)
                else:
                    utils.log(
                        f"Retrieved {len(ts_df)} rows for station "
                        f"'{_station_id}' from 'recent' data."
                    )

        return ts_df

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

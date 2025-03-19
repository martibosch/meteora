"""National Oceanic And Atmospheric Administration (NOAA) client."""

import shutil
import tempfile
from collections.abc import Sequence

import dask
import pandas as pd
import polars as pl
import pooch
import pyproj
from dask import diagnostics

from meteora import settings
from meteora.clients.base import BaseTextClient
from meteora.mixins import StationsEndpointMixin, VariablesHardcodedMixin
from meteora.utils import DateTimeType, KwargsType, PathType, RegionType, VariablesType

# disable pooch warnings when providing `None` as "known_hash"
logger = pooch.get_logger()
logger.setLevel("WARNING")


# API endpoints
BASE_URL = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly"
GHCNH_STATIONS_ENDPOINT = f"{BASE_URL}/doc/ghcnh-station-list.csv"
TS_ENDPOINT = f"{BASE_URL}/access/by-station/" + "GHCNh_{station_id}_por.psv"

# for pooch
# TODO: how often can it change? how to properly update it if it does?
STATIONS_LIST_KNOWN_HASH = (
    "6b837d8d953aa6ebc172755864e549518944e7bec15b2196ee191219587a96f5"
)

# useful constants
STATIONS_ID_COL = "id"
VARIABLES_ID_COL = "code"
VARIABLES_LABEL_COL = "description"
TIME_COL = "time"  # there is no label for time on the returned json, we generate it
GHCNH_STATIONS_COLUMNS = [
    "id",
    "latitude",
    "longitude",
    "elevation",
    "state",
    "name",
    "gsn_flag",
    "hcn_crn_flag",
    "wmo_id",
]
GHCNH_STATIONS_COLSPECS = [
    (0, 11),
    (12, 21),
    (22, 32),
    (33, 40),
    (41, 44),
    (45, 76),
    (77, 81),
    (82, 86),
    (87, 93),
]

# see section "IV. List of elements/variable" and appendix A of the GHCNh documentation
# www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/
# ghcnh_DOCUMENTATION.pdf
VARIABLES_DICT = {
    "temperature": "2 meter (circa) Above Ground Level Air (dry bulb) Temperature (⁰C "
    "to tenths)",
    "relative_humidity": "Depending on the source, relative humidity is either measured"
    " directly or calculated from air (dry bulb) temperature and dew point temperature "
    "(whole percent)",
    "station_level_pressure": "The pressure that is observed at a specific elevation "
    "and is the true barometric pressure of a location. It is the pressure exerted by "
    "the atmosphere at a point as a result of gravity acting upon the 'column' of air "
    "that lies directly above the point. (hPa)",
    "precipitation": "Total liquid precipitation (rain or melted snow). Totals are "
    "nominally for the hour, but may include intermediate reports within the hour. "
    "Please refer to Appendix B for important details on precipitation totals; a `T` in"
    " the measurement code column indicates a trace amount of precipitation "
    "(millimeters).",
    "wind_speed": "Wind speed (meters per second)",
    "wind_direction": "Wind Direction from true north using compass directions (e.g. "
    "360 = true north, 180 = south, 270 = west, etc.). Note: A direction of `000` is "
    "given for calm winds. (whole degrees)",
}
ECV_DICT = {
    "preciptation": "precipitation",
    "pressure": "station_level_pressure",
    "surface_wind_speed": "wind_speed",
    "surface_wind_direction": "wind_direction",
    "temperature": "temperature",
    "water_vapour": "relative_humidity",
}

# ACHTUNG: note that in the time series data frame the station column label is "Station
# ID" whereas in the stations data frame it is "id".
TS_STATION_ID_COL = "Station_ID"
TS_DATETIME_COLS = ["Year", "Month", "Day", "Hour", "Minute"]


class GHCNHourlyClient(StationsEndpointMixin, VariablesHardcodedMixin, BaseTextClient):
    """NOAA GHCN hourly client."""

    # ACHTUNG: many constants are set in `GHCNH_STATIONS_COLUMNS` above
    # geom constants
    X_COL = "longitude"
    Y_COL = "latitude"
    CRS = pyproj.CRS("epsg:4326")

    # API endpoints
    _stations_endpoint = GHCNH_STATIONS_ENDPOINT
    _ts_endpoint = TS_ENDPOINT

    # data frame labels constants
    _stations_id_col = STATIONS_ID_COL
    _variables_id_col = VARIABLES_ID_COL
    _variables_label_col = VARIABLES_LABEL_COL
    _variables_dict = VARIABLES_DICT
    _ecv_dict = ECV_DICT
    _time_col = TIME_COL

    def __init__(
        self,
        region: RegionType,
        *,
        pooch_dir: PathType | None = None,
        **sjoin_kwargs: KwargsType,
    ) -> None:
        """Initialize GHCN hourly client."""
        self.region = region
        if sjoin_kwargs is None:
            sjoin_kwargs = settings.SJOIN_KWARGS.copy()
        self.SJOIN_KWARGS = sjoin_kwargs

        # set pooch directory for caching file downloads
        if pooch_dir is None:
            pooch_dir = tempfile.mkdtemp()
            self._tmp_dir = True
        self.pooch_dir = pooch_dir
        # self.pooch = pooch.Pooch(self.working_dir, BASE_URL)
        self.pooch_kwargs = {"path": self.pooch_dir}

        # need to call super().__init__() to set the cache
        super().__init__()

    def __del__(self) -> None:
        """Destructor to clean up temporary files."""
        if getattr(self, "_tmp_dir", False):
            shutil.rmtree(self.pooch_dir)

    def _get_stations_df(self) -> pd.DataFrame:
        """Get all stations."""
        try:
            # ACHTUNG: we are not using `self.pooch_kwargs` to set the path to download
            # files, because the stations file path can be reused independently of the
            # region, so it is useful to cache it globally
            stations_filepath = pooch.retrieve(
                self._stations_endpoint, STATIONS_LIST_KNOWN_HASH
            )
        except ValueError:
            # sha hash mismatch, probably because of updates in the station list
            stations_filepath = pooch.retrieve(self._stations_endpoint, None)
        return pd.read_fwf(
            stations_filepath,
            colspecs=GHCNH_STATIONS_COLSPECS,
            names=GHCNH_STATIONS_COLUMNS,
        )

    def _ts_params(
        self, variable_ids: Sequence, start: DateTimeType, end: DateTimeType
    ) -> dict:
        # process date args
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)

        return dict(variable_ids=variable_ids, start=start, end=end)

    def _ts_df_from_endpoint(self, ts_params) -> pd.DataFrame:
        """Get time series data frame from endpoint."""
        # we override this method because we need a separate request for each station
        variable_cols = list(ts_params["variable_ids"])
        cols_to_keep = variable_cols + [TS_STATION_ID_COL]

        # use dask to parallelize requests
        def _process_station_ts_df(station_id):
            station_ts_filepath = pooch.retrieve(
                self._ts_endpoint.format(station_id=station_id),
                None,
                **self.pooch_kwargs,
            )
            ts_df = (
                pl.scan_csv(
                    station_ts_filepath,
                    separator="|",
                    has_header=True,
                )
                .with_columns(
                    # return null for invalid dates instead of raising a `ComputeError`
                    # (needed because of invalid dates in GHCNh data)
                    pl.datetime(
                        *[pl.col(col) for col in TS_DATETIME_COLS], ambiguous="null"
                    ).alias("time")
                )
                .select(cols_to_keep + ["time"])
                .filter(
                    pl.col("time").is_not_null()
                    & pl.col("time").is_between(
                        ts_params["start"],
                        ts_params["end"],
                        closed="both",
                    )
                )
            )
            return ts_df.collect().to_pandas()

        tasks = [
            dask.delayed(_process_station_ts_df)(station_id)
            for station_id in self.stations_gdf[self._stations_id_col]
        ]
        with diagnostics.ProgressBar():
            ts_dfs = dask.compute(*tasks)

        # concat only data frames with non-empty data for the requested variables
        def _drop_empty_object_columns(ts_df):
            df_objects = ts_df.select_dtypes(object)
            return ts_df[
                ts_df.columns.difference(df_objects.columns[df_objects.isna().all()])
            ]

        return pd.concat(
            [_drop_empty_object_columns(ts_df) for ts_df in ts_dfs if not ts_df.empty],
            axis="rows",
        ).set_index([TS_STATION_ID_COL, self._time_col])

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
            Target variables, which can be either an GHCNh variable code (string) or an
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

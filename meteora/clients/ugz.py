"""Environmental and health protection (UGZ) of the city of Zurich."""

import pyproj
from pyregeon import RegionType

from meteora import settings
from meteora.clients.base import BaseFileClient
from meteora.clients.mixins import StationsEndpointMixin, VariablesHardcodedMixin
from meteora.utils import KwargsType

# API endpoints
STATIONS_ENDPOINT = (
    "https://data.stadt-zuerich.ch/dataset/"
    "ugz_stadtklima_zuerich_messorte_messnetz_meteoblue/download/"
    "ugz_stadtklima_zuerich_messorte_messnetz_meteoblue.csv"
)
TS_ENDPOINT = (
    "https://www.web.statistik.zh.ch/awel/LoRa/data/"
    "AWEL_Sensors_LoRa_{year}{month:02}.csv"
)

# useful constants
STATIONS_GDF_ID_COL = "locationID"
TS_DF_STATIONS_ID_COL = "locationID"
TS_DF_TIME_COL = "timestamp"
VARIABLES_ID_COL = "code"
VARIABLES_LABEL_COL = "description"

VARIABLES_DICT = {
    "temperature": "measured value air temperature (in °C)",
}
ECV_DICT = {
    "T": "temperature",
}


class UGZClient(StationsEndpointMixin, VariablesHardcodedMixin, BaseFileClient):
    """UGZ client (city of Zurich).

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
    sensor_height : {1, 1.8, 2, 2.5, 2.7, 3.5, 4}, default 2
        Sensor height (in m) above site location, must be a value among the following:
        1, 1.8, 2, 2.5, 2.7, 3.5, 4. The default value is 2 m.
    pooch_kwargs : dict, optional
        Keyword arguments to pass to the `pooch.retrieve` function when caching file
        downloads.
    sjoin_kwargs : dict, optional
        Keyword arguments to pass to the `geopandas.sjoin` function when filtering the
        stations within the region. If None, the value from `settings.SJOIN_KWARGS` is
        used.
    """

    # ACHTUNG: many constants are set in `GHCNH_STATIONS_COLUMNS` above
    # geom constants
    X_COL = "EKoord"
    Y_COL = "NKoord"
    CRS = pyproj.CRS("epsg:2056")

    # API endpoints
    _stations_endpoint = STATIONS_ENDPOINT
    # _ts_endpoint = TS_ENDPOINT
    _stations_read_csv_kwargs = {"encoding": "utf-8"}

    # data frame labels constants
    _stations_gdf_id_col = STATIONS_GDF_ID_COL
    _ts_df_stations_id_col = TS_DF_STATIONS_ID_COL
    _ts_df_time_col = TS_DF_TIME_COL
    _variables_id_col = VARIABLES_ID_COL
    _variables_label_col = VARIABLES_LABEL_COL
    _variables_dict = VARIABLES_DICT
    _ecv_dict = ECV_DICT

    def __init__(
        self,
        region: RegionType,
        *,
        pooch_kwargs: KwargsType | None = None,
        **sjoin_kwargs: KwargsType,
    ) -> None:
        """Initialize GHCN hourly client."""
        self.region = region
        if not sjoin_kwargs:
            sjoin_kwargs = settings.SJOIN_KWARGS.copy()
        self.SJOIN_KWARGS = sjoin_kwargs
        if pooch_kwargs is None:
            pooch_kwargs = {}
        self.pooch_kwargs = pooch_kwargs

        # need to call super().__init__() to set the cache
        super().__init__()

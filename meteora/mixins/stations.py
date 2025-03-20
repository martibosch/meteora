"""Stations mixins."""

from abc import ABC

import geopandas as gpd
import pandas as pd

from meteora import settings
from meteora.utils import abstract_attribute


class StationsEndpointMixin(ABC):
    """Stations endpoint mixin."""

    @abstract_attribute
    def _stations_endpoint(self) -> str:
        pass

    @abstract_attribute
    def _stations_gdf_id_col(self) -> str:
        """Column with the station IDs in the `stations_gdf` returned by the API."""
        pass

    def _get_stations_df(self) -> pd.DataFrame:
        """Get the stations dataframe for the instance.

        Returns
        -------
        stations_df : pandas.DataFrame
            The stations data for the given region.

        """
        response_content = self._get_content_from_url(self._stations_endpoint)
        return self._stations_df_from_content(response_content)

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

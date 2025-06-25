"""Stations mixins."""

from abc import ABC

import pandas as pd

from meteora import utils


class StationsEndpointMixin(ABC):
    """Stations endpoint mixin."""

    @utils.abstract_attribute
    def _stations_endpoint(self) -> str:
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

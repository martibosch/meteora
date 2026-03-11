"""Time series mixins."""

import abc
from collections.abc import Iterable, Mapping

import pandas as pd


class PartitionedTSMixin(abc.ABC):
    """Base mixin for partitioned time series endpoints.

    Subclasses partition time series requests along one axis (time, variable, or
    station) and iterate over the partitions.  When ``client.progress`` is
    enabled, only the outermost partitioned mixin in the MRO displays a tqdm
    progress bar, determined by ``_should_show_progress``.
    """

    def _should_show_progress(self, mixin_cls):
        """Return whether *mixin_cls* should display a progress bar.

        Returns ``True`` only when ``self.progress`` is truthy **and**
        *mixin_cls* is the first ``PartitionedTSMixin`` subclass in the MRO
        that defines its own ``_ts_df_from_endpoint``.  This ensures that only
        the outermost partition loop shows a progress bar, avoiding nested bars.
        """
        if not getattr(self, "progress", False):
            return False
        # find the first class in MRO that defines its own _ts_df_from_endpoint
        # (skips the concrete client class and PartitionedTSMixin itself)
        for cls in type(self).__mro__:
            if (
                cls is not PartitionedTSMixin
                and issubclass(cls, PartitionedTSMixin)
                and "_ts_df_from_endpoint" in cls.__dict__
            ):
                return cls is mixin_cls
        return False

    def _concat_ts_dfs(self, ts_dfs: Iterable[pd.DataFrame | pd.Series], axis: int):
        ts_dfs = [ts_df for ts_df in ts_dfs if ts_df is not None]
        if not ts_dfs:
            return pd.DataFrame()
        non_empty = [ts_df for ts_df in ts_dfs if not ts_df.empty]
        if not non_empty:
            return ts_dfs[0]
        if len(non_empty) == 1:
            return non_empty[0]
        return pd.concat(non_empty, axis=axis)


class TimePartitionedTSMixin(PartitionedTSMixin):
    """Time-partitioned time series mixin.

    Either set the ``_time_partition_freq`` attribute to a pandas frequency string
    (e.g., ``"D"``, ``"MS"``, ``"YS"``) or override ``_iter_time_partitions`` for
    non-standard periods.  Each partition dict must contain a ``"period"`` key whose
    value is a datetime-like that can be referenced in ``_ts_endpoint`` as
    ``{period}``, ``{period.year}``, ``{period.month:02d}``, etc.

    When this is the outermost partitioned mixin and ``progress`` is enabled, a
    tqdm bar labelled *Time periods* is shown.
    """

    _time_partition_freq: str

    def _iter_time_partitions(self, ts_params: Mapping) -> Iterable[dict]:
        start = pd.Timestamp(ts_params["start"])
        end = pd.Timestamp(ts_params["end"])
        # snap start to the beginning of the period so the first partition is not missed
        # when start falls in the middle of a period
        snapped_start = pd.tseries.frequencies.to_offset(
            self._time_partition_freq
        ).rollback(start)
        date_range = pd.date_range(
            start=snapped_start, end=end, freq=self._time_partition_freq
        )
        if len(date_range) == 0:
            date_range = [snapped_start]
        return [{"period": date} for date in date_range]

    def _ts_df_from_endpoint(self, ts_params: Mapping) -> pd.DataFrame:
        partitions = self._iter_time_partitions(ts_params)
        if self._should_show_progress(TimePartitionedTSMixin):
            from tqdm.auto import tqdm

            partitions = tqdm(partitions, desc="Time periods", unit="period")
        ts_dfs = [
            super()._ts_df_from_endpoint(ts_params | partition)
            for partition in partitions
        ]
        return self._concat_ts_dfs(ts_dfs, axis=0)


class VariablePartitionedTSMixin(PartitionedTSMixin):
    """Variable-partitioned time series mixin.

    When this is the outermost partitioned mixin and ``progress`` is enabled, a
    tqdm bar labelled *Variables* is shown.
    """

    _ts_variable_endpoint_key = "variable_id"

    def _iter_variable_partitions(self, ts_params: Mapping) -> Iterable[dict]:
        variable_ids = list(ts_params["variable_ids"])
        return [
            {self._ts_variable_endpoint_key: variable_id}
            for variable_id in variable_ids
        ]

    def _format_variable_ts_df(
        self, ts_df: pd.DataFrame | pd.Series, variable_id
    ) -> pd.DataFrame | pd.Series:
        if isinstance(ts_df, pd.Series):
            return ts_df.rename(variable_id)
        return ts_df

    def _ts_df_from_endpoint(self, ts_params: Mapping) -> pd.DataFrame:
        partitions = self._iter_variable_partitions(ts_params)
        if self._should_show_progress(VariablePartitionedTSMixin):
            from tqdm.auto import tqdm

            partitions = tqdm(partitions, desc="Variables", unit="var")
        ts_dfs = []
        for partition in partitions:
            variable_id = partition[self._ts_variable_endpoint_key]
            ts_df = super()._ts_df_from_endpoint(ts_params | partition)
            ts_df = self._format_variable_ts_df(ts_df, variable_id)
            ts_dfs.append(ts_df)
        return self._concat_ts_dfs(ts_dfs, axis=1)


class StationPartitionedTSMixin(PartitionedTSMixin):
    """Station-partitioned time series mixin.

    When this is the outermost partitioned mixin and ``progress`` is enabled, a
    tqdm bar labelled *Stations* is shown.
    """

    _ts_station_endpoint_key = "station_id"

    def _iter_station_ids(self) -> Iterable:
        return self.stations_gdf.index

    def _iter_station_partitions(self, ts_params: Mapping) -> Iterable[dict]:
        return [
            {self._ts_station_endpoint_key: station_id}
            for station_id in self._iter_station_ids()
        ]

    def _ts_df_from_endpoint(self, ts_params: Mapping) -> pd.DataFrame:
        partitions = self._iter_station_partitions(ts_params)
        if self._should_show_progress(StationPartitionedTSMixin):
            from tqdm.auto import tqdm

            partitions = tqdm(partitions, desc="Stations", unit="station")
        ts_dfs = [
            super()._ts_df_from_endpoint(ts_params | partition)
            for partition in partitions
        ]
        return self._concat_ts_dfs(ts_dfs, axis=0)

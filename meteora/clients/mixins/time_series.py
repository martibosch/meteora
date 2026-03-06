"""Time series mixins."""

import abc
from collections.abc import Iterable, Mapping

import pandas as pd


class PartitionedTSMixin(abc.ABC):
    """Base mixin for partitioned time series endpoints."""

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

    Either set the `time_partiton_freq` attribute to a pandas frequency string, (e.g.,
    "D", "MS", "YS") or override `_iter_time_partitions` for non-standard periods.  Each
    partition dict must contain a "period" key whose value is a date-time like that can
    be referenced in `_ts_endpoint` as `{period}`, `{period.year}`,
    `{period.month:02d}`, etc.
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
        ts_dfs = [
            super()._ts_df_from_endpoint(ts_params | partition)
            for partition in self._iter_time_partitions(ts_params)
        ]
        return self._concat_ts_dfs(ts_dfs, axis=0)


class VariablePartitionedTSMixin(PartitionedTSMixin):
    """Variable-partitioned time series mixin."""

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
        ts_dfs = []
        for partition in self._iter_variable_partitions(ts_params):
            variable_id = partition[self._ts_variable_endpoint_key]
            ts_df = super()._ts_df_from_endpoint(ts_params | partition)
            ts_df = self._format_variable_ts_df(ts_df, variable_id)
            ts_dfs.append(ts_df)
        return self._concat_ts_dfs(ts_dfs, axis=1)


class StationPartitionedTSMixin(PartitionedTSMixin):
    """Station-partitioned time series mixin."""

    _ts_station_endpoint_key = "station_id"

    def _iter_station_ids(self) -> Iterable:
        return self.stations_gdf.index

    def _iter_station_partitions(self, ts_params: Mapping) -> Iterable[dict]:
        return [
            {self._ts_station_endpoint_key: station_id}
            for station_id in self._iter_station_ids()
        ]

    def _ts_df_from_endpoint(self, ts_params: Mapping) -> pd.DataFrame:
        ts_dfs = [
            super()._ts_df_from_endpoint(ts_params | partition)
            for partition in self._iter_station_partitions(ts_params)
        ]
        return self._concat_ts_dfs(ts_dfs, axis=0)

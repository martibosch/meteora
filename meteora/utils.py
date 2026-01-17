"""Utils.

Based on osmnx utils and downloader modules.
"""

import datetime as dt
import logging as lg
import os
import sys
import unicodedata
from collections.abc import Callable, Mapping
from contextlib import redirect_stdout
from pathlib import Path
from typing import TypeVar

import geopandas as gpd
import numpy as np
import pandas as pd

from meteora import settings

try:
    import xarray as xr
    import xvec  # noqa: F401
except ImportError:
    xr = None

VariablesType = str | int | list[str] | list[int]
DateTimeType = dt.date | dt.datetime | np.datetime64 | pd.Timestamp | str | int | float
KwargsType = Mapping | None
PathType = str | os.PathLike
if xr is not None:
    CubeType = xr.Dataset
else:
    CubeType = TypeVar("CubeType")
AggFuncType = str | Callable | None


########################################################################################
# geo utils
def dms_to_decimal(ser: pd.Series) -> pd.Series:
    """Convert a series from degrees, minutes, seconds (DMS) to decimal degrees."""
    degrees = ser.str[0:2].astype(int)
    minutes = ser.str[2:4].astype(int)
    seconds = ser.str[4:6].astype(int)
    direction = ser.str[-1]

    decimal = degrees + minutes / 60 + seconds / 3600
    decimal = decimal.where(direction.isin(["N", "E"]), -decimal)

    return decimal


########################################################################################
# data structure utils
def long_to_wide(
    ts_df: pd.DataFrame, *, variables: VariablesType | None = None
) -> pd.DataFrame:
    """Convert a time series data frame from long (default) to wide format.

    Parameters
    ----------
    ts_df : pd.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    variables : str, int or list-like of str or int, optional
        Target variables, which must be columns in `ts_df`.

    Returns
    -------
    wide_ts_df : pd.DataFrame
        Wide form data frame with a time series of measurements (index) for each
        variable (first-level column index) at each station (second-level column index).
        If there is only one variable, the column index is a single level featuring the
        stations.
    """
    # despite ruff rule PD010, use unstack which is both simpler and faster
    # https://docs.astral.sh/ruff/rules/pandas-use-of-dot-pivot-or-unstack
    rename_col_level = True
    if variables is None:
        variables = ts_df.columns
    if pd.api.types.is_list_like(variables) and len(variables) == 1:
        variables = variables[0]
        rename_col_level = False
    wide_ts_df = ts_df[variables].unstack(level=ts_df.index.names[0])
    # rename the variables column level (if we have it - i.e., multivariate case)
    if rename_col_level:
        wide_ts_df = wide_ts_df.rename_axis(columns={None: "variable"})
    return wide_ts_df


def long_to_cube(
    ts_df: pd.DataFrame,
    stations_gdf: gpd.GeoDataFrame,
) -> CubeType:
    """Convert a time series data frame and station locations to a vector data cube.

    A vector data cube is an n-D array with at least one dimension indexed by vector
    geometries. In Python, this is represented as an xarray Dataset (or DataArray)
    object with an indexed dimension with vector geometries set using xvec.

    Parameters
    ----------
    ts_df : pd.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    stations_gdf : gpd.GeoDataFrame
        The stations data as a GeoDataFrame.

    Returns
    -------
    ts_cube : xr.Dataset
        The vector data cube with the time series of measurements for each station. The
        stations are indexed by their geometry.
    """
    # get the stations id column in the time series data frame
    stations_ts_df_id_col = ts_df.index.names[0]
    # convert data frame to xarray
    ts_ds = ts_df.to_xarray()
    # get only the station ids and geometries from the stations at `ts_df`
    stations_gser = stations_gdf.loc[ts_ds[stations_ts_df_id_col].values]["geometry"]
    return (
        # assign the stations geometries as indexed dimension for xvec
        ts_ds.assign_coords({stations_ts_df_id_col: stations_gser.values})
        .rename({stations_ts_df_id_col: "geometry"})
        .xvec.set_geom_indexes("geometry", crs=stations_gdf.crs)
        # add station id labels as dimensionless coordinates associated to the geometry
        .assign_coords(
            {
                stations_ts_df_id_col: (
                    "geometry",
                    stations_gser.index,
                )
            }
        )
    )


########################################################################################
# meteo utils
def get_heatwave_periods(
    ts_df: pd.DataFrame,
    *,
    heatwave_t_threshold: float | None = None,
    heatwave_n_consecutive_days: int | None = None,
    station_agg_func: AggFuncType = None,
    inter_station_agg_func: AggFuncType = None,
) -> list[tuple[dt.date, dt.date]]:
    """Get the heatwave periods from a time series of temperature measurements.

    A heatwave is defined as a period of at least `heatwave_n_consecutive_days` days
    with a temperature above `heatwave_t_threshold`.

    Parameters
    ----------
    ts_df : pd.DataFrame
        Data frame with a time series of temperature measurements at each station, in
        long or wide format.
    heatwave_t_threshold : float, optional
        The temperature threshold for a heatwave, in units of `ts_df`. If not provided,
        the value from `settings.HEATWAVE_T_THRESHOLD` is used.
    heatwave_n_consecutive_days : int, optional
        The number of consecutive days above the mean temperature threshold for the
        corresponding period to be  considered a heatwave. If not provided, the value
        from `settings.HEATWAVE_N_CONSECUTIVE_DAYS` is used.
    station_agg_func, inter_station_agg_func : str or function, optional
        How to respectively aggregate the daily temperature measurements at each station
        and the aggregated daily temperature measurements across all stations. Must be a
        string function name or a callable function, which will be passed as the `func`
        argument of `pandas.core.groupby.DataFrameGroupBy.agg`. If not provided, the
        respective values from `settings.HEATWAVE_STATION_AGG_FUNC` and
        `settings.HEATWAVE_INTER_STATION_AGG_FUNC` are used.

    Returns
    -------
    heatwave_range_df : pd.DataFrame
        Data frame with the heatwave start and end dates as columns, indexed by the
        heatwave event identifier.
    """
    # if using a multi-index, assume that it is a long-form data frame so transform it
    if isinstance(ts_df.index, pd.MultiIndex):
        # ACHTUNG: we are assuming that there is a single column with the temperature
        ts_df = long_to_wide(ts_df, variables=ts_df.columns[0])

    # process arguments
    if heatwave_t_threshold is None:
        heatwave_t_threshold = settings.HEATWAVE_T_THRESHOLD
    if heatwave_n_consecutive_days is None:
        heatwave_n_consecutive_days = settings.HEATWAVE_N_CONSECUTIVE_DAYS
    if station_agg_func is None:
        station_agg_func = settings.HEATWAVE_STATION_AGG_FUNC
    if inter_station_agg_func is None:
        inter_station_agg_func = settings.HEATWAVE_INTER_STATION_AGG_FUNC

    # find consecutive days above threshold
    day_agg_ts_ser = (
        ts_df.groupby(ts_df.index.date)
        .agg(station_agg_func)
        .agg(inter_station_agg_func, axis="columns")
    )

    ge_sel_ser = day_agg_ts_ser.ge(heatwave_t_threshold)
    consecutive_ge_ser = (
        day_agg_ts_ser[ge_sel_ser]
        .index.to_series()
        .groupby((~ge_sel_ser).cumsum())
        .agg(["first", "last", "count"])
    )

    return [
        (
            dt.datetime.combine(row["first"], dt.time.min),
            dt.datetime.combine(row["last"], dt.time.max),
        )
        for i, row in consecutive_ge_ser[
            consecutive_ge_ser["count"].ge(heatwave_n_consecutive_days)
        ].iterrows()
    ]


def get_heatwave_ts_df(
    ts_df: pd.DataFrame,
    *,
    heatwave_periods: list[tuple[dt.date, dt.date]] | None = None,
    heatwave_t_threshold: float | None = None,
    heatwave_n_consecutive_days: int | None = None,
    station_agg_func: str | None = None,
    inter_station_agg_func: str | None = None,
) -> pd.DataFrame:
    """Get a time series data frame for the heatwave periods.

    A heatwave is defined as a period of at least `heatwave_n_consecutive_days` days
    with a temperature above `heatwave_t_threshold`.

    Parameters
    ----------
    ts_df : pd.DataFrame
        Data frame with a time series of temperature measurements at each station, in
        long or wide format.
    heatwave_t_threshold : float, optional
        The temperature threshold for a heatwave, in units of `ts_df`. If not provided,
        the value from `settings.HEATWAVE_T_THRESHOLD` is used.
    heatwave_n_consecutive_days : int, optional
        The number of consecutive days above the mean temperature threshold for the
        corresponding period to be  considered a heatwave. If not provided, the value
        from `settings.HEATWAVE_N_CONSECUTIVE_DAYS` is used.
    station_agg_func, inter_station_agg_func : str or function, optional
        How to respectively aggregate the daily temperature measurements at each station
        and the aggregated daily temperature measurements across all stations. Must be a
        string function name or a callable function, which will be passed as the `func`
        argument of `pandas.core.groupby.DataFrameGroupBy.agg`. If not provided, the
        respective values from `settings.HEATWAVE_STATION_AGG_FUNC` and
        `settings.HEATWAVE_INTER_STATION_AGG_FUNC` are used.

    Returns
    -------
    heatwave_range_df : pd.DataFrame
        Data frame with the heatwave start and end dates as columns, indexed by the
        heatwave event identifier.
    """
    if heatwave_periods is None:
        heatwave_periods = get_heatwave_periods(
            ts_df,
            heatwave_t_threshold=heatwave_t_threshold,
            heatwave_n_consecutive_days=heatwave_n_consecutive_days,
            station_agg_func=station_agg_func,
            inter_station_agg_func=inter_station_agg_func,
        )
    if heatwave_periods:
        return (
            pd.concat(
                ts_df.loc[heatwave_start:heatwave_end].assign(
                    heatwave=f"{heatwave_start.date()}/{heatwave_end.date()}"
                )
                for heatwave_start, heatwave_end in heatwave_periods
            )
            .reset_index()
            .set_index(["heatwave", ts_df.index.name])
        )
    else:
        log(
            "No heatwave periods found, returning empty data frame.",
            level=lg.WARNING,
        )
        return pd.DataFrame(
            columns=ts_df.columns,
            index=pd.MultiIndex(
                levels=[[], []], codes=[[], []], names=["heatwave", ts_df.index.name]
            ),
        )


########################################################################################
# abstract attribute
# `DummyAttribute` and `abstract_attribute` below are hardcoded from
# github.com/rykener/better-abc to avoid relying on an unmaintained library that is not
# in conda-forge
class DummyAttribute:
    """Dummy attribute."""

    pass


def abstract_attribute(obj=None):
    """Abstract attribute."""
    if obj is None:
        obj = DummyAttribute()
    obj.__is_abstract_attribute__ = True
    return obj


########################################################################################
# logging
def ts(*, style: str = "datetime", template: str | None = None) -> str:
    """Get current timestamp as string.

    Parameters
    ----------
    style : str {"datetime", "date", "time"}
        Format the timestamp with this built-in template.
    template : str, optional
        If not None, format the timestamp with this template instead of one of the
        built-in styles.

    Returns
    -------
    ts : str
        The string timestamp.
    """
    if template is None:
        if style == "datetime":
            template = "{:%Y-%m-%d %H:%M:%S}"
        elif style == "date":
            template = "{:%Y-%m-%d}"
        elif style == "time":
            template = "{:%H:%M:%S}"
        else:  # pragma: no cover
            raise ValueError(f"unrecognized timestamp style {style!r}")

    ts = template.format(dt.datetime.now())
    return ts


def _get_logger(level: int, name: str, filename: str) -> lg.Logger:
    """Create a logger or return the current one if already instantiated.

    Parameters
    ----------
    level : int
        One of Python's logger.level constants.
    name : string
        Name of the logger.
    filename : string
        Name of the log file, without file extension.

    Returns
    -------
    logger : logging.logger
    """
    logger = lg.getLogger(name)

    # if a logger with this name is not already set up
    if not getattr(logger, "handler_set", None):
        # get today's date and construct a log filename
        log_filename = Path(settings.LOGS_FOLDER) / f"{filename}_{ts(style='date')}.log"

        # if the logs folder does not already exist, create it
        log_filename.parent.mkdir(parents=True, exist_ok=True)

        # create file handler and log formatter and set them up
        handler = lg.FileHandler(log_filename, encoding="utf-8")
        formatter = lg.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.handler_set = True

    return logger


def log(
    message: str,
    *,
    level: int | None = None,
    name: str | None = None,
    filename: str | None = None,
) -> None:
    """Write a message to the logger.

    This logs to file and/or prints to the console (terminal), depending on the current
    configuration of settings.LOG_FILE and settings.LOG_CONSOLE.

    Parameters
    ----------
    message : str
        The message to log.
    level : int, optional
        One of Python's logger.level constants. If None, the value from
        `settings.LOG_LEVEL` is used.
    name : str, optional
        Name of the logger. If None, the value from `settings.LOG_NAME` is used.
    filename : str, optional
        Name of the log file, without file extension. If None, the value from
        `settings.LOG_FILENAME` is used.
    """
    if level is None:
        level = settings.LOG_LEVEL
    if name is None:
        name = settings.LOG_NAME
    if filename is None:
        filename = settings.LOG_FILENAME

    # if logging to file is turned on
    if settings.LOG_FILE:
        # get the current logger (or create a new one, if none), then log message at
        # requested level
        logger = _get_logger(level=level, name=name, filename=filename)
        if level == lg.DEBUG:
            logger.debug(message)
        elif level == lg.INFO:
            logger.info(message)
        elif level == lg.WARNING:
            logger.warning(message)
        elif level == lg.ERROR:
            logger.error(message)

    # if logging to console (terminal window) is turned on
    if settings.LOG_CONSOLE:
        # prepend timestamp
        message = f"{ts()} {message}"

        # convert to ascii so it doesn't break windows terminals
        message = (
            unicodedata.normalize("NFKD", str(message))
            .encode("ascii", errors="replace")
            .decode()
        )

        # print explicitly to terminal in case jupyter notebook is the stdout
        if getattr(sys.stdout, "_original_stdstream_copy", None) is not None:
            # redirect captured pipe back to original
            os.dup2(sys.stdout._original_stdstream_copy, sys.__stdout__.fileno())
            sys.stdout._original_stdstream_copy = None
        with redirect_stdout(sys.__stdout__):
            print(message, file=sys.__stdout__, flush=True)

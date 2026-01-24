"""Climate indices with xclim integration."""

import inspect
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeAlias

import pandas as pd

from meteora import settings
from meteora.optional import require_optional

try:
    import xarray as xr
except ImportError:
    xr = None
try:
    import xclim.indices as xci
except ImportError:
    xci = None

if TYPE_CHECKING:
    import xarray as xr_type

    DataArrayType: TypeAlias = xr_type.DataArray
else:
    DataArrayType: TypeAlias = Any

__all__ = [
    "cooling_degree_days",
    "heating_degree_days",
    "frost_days",
    "ice_days",
    "heat_index",
    "hot_days",
    "hot_spell_frequency",
    "hot_spell_total_length",
    "humidex",
    "daily_temperature_range",
    "prcptot",
    "wetdays",
    "dry_days",
    "max_1day_precipitation_amount",
    "max_n_day_precipitation_amount",
    "sfc_wind_mean",
    "sfc_wind_max",
    "sfc_wind_min",
    "windy_days",
    "tn_days_above",
]

_CLIMATE_INDICES_FEATURE = "meteora.climate_indices"


def _require_xclim(feature: str = _CLIMATE_INDICES_FEATURE) -> None:
    require_optional(
        {"xarray": xr, "xclim": xci},
        extra="xclim",
        feature=feature,
    )


def _get_single_col(ts_df: pd.DataFrame, col: str | None) -> str:
    """Return a column name, defaulting to the first column if None."""
    if col is None:
        if len(ts_df.columns) == 0:
            raise ValueError("ts_df must have at least one column to infer a column.")
        return ts_df.columns[0]
    return col


def _get_units_from_dtype(dtype) -> str | None:
    """Extract a units string from a dtype when using pint-pandas."""
    unit = getattr(dtype, "units", None)
    if unit is not None:
        return str(unit)
    dtype_str = str(dtype)
    if dtype_str.startswith("pint[") and dtype_str.endswith("]"):
        return dtype_str[len("pint[") : -1]
    return None


def _get_units_map(ts_df: pd.DataFrame) -> Mapping:
    """Return the units metadata mapping for a DataFrame, if any."""
    units_map: dict = {}
    attrs_units = ts_df.attrs.get("units")
    if isinstance(attrs_units, Mapping):
        units_map.update(attrs_units)
    for col, dtype in ts_df.dtypes.items():
        if col in units_map:
            continue
        unit = _get_units_from_dtype(dtype)
        if unit is not None:
            units_map[col] = unit
    return units_map


def _resolve_unit(ts_df: pd.DataFrame, variable: str, unit: str) -> str:
    """Resolve a column's unit, preferring DataFrame metadata when available."""
    units_map = _get_units_map(ts_df)
    resolved_unit = units_map.get(variable)
    return unit if resolved_unit is None else resolved_unit


def _get_col_or_default(col: str | None, default: str) -> str:
    """Return the column name or a provided default when None."""
    return default if col is None else col


def _get_xclim_default(func_name: str, param_name: str):
    """Fetch a parameter default from an xclim function signature."""
    _require_xclim()
    func = getattr(xci, func_name, None)
    if func is None:
        raise ValueError(f"xclim has no function {func_name!r}.")
    param = inspect.signature(func).parameters.get(param_name)
    if param is None:
        raise ValueError(f"{func_name} has no parameter {param_name!r}.")
    if param.default is inspect._empty:
        raise ValueError(f"{func_name}.{param_name} has no default.")
    return param.default


def _to_xarray(ts_df: pd.DataFrame, variable: str, unit: str) -> DataArrayType:
    """Convert a column of a time series data frame to a units-aware DataArray."""
    _require_xclim()
    ts_da = ts_df[variable].to_xarray()
    resolved_unit = _resolve_unit(ts_df, variable, unit)
    if resolved_unit is not None:
        ts_da.attrs["units"] = resolved_unit
    return ts_da


def _to_xarray_resampled(
    ts_df: pd.DataFrame,
    variable: str,
    unit: str,
    *,
    freq: str,
    agg: str,
) -> DataArrayType:
    """Convert a column to a resampled, units-aware DataArray."""
    ts_da = _to_xarray(ts_df, variable, unit)
    resampler = ts_da.resample(**{"time": freq})
    return getattr(resampler, agg)()


def _to_pandas(ts_da: DataArrayType) -> pd.DataFrame:
    """Convert a DataArray to a DataFrame with stations as columns."""
    ts_da = ts_da.transpose("time", "station_id")
    pint_accessor = getattr(ts_da, "pint", None)
    if pint_accessor is not None:
        try:
            ts_da = pint_accessor.dequantify()
        except Exception:
            pass
    return ts_da.to_pandas()


def cooling_degree_days(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    freq: str | None = None,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
):
    """Compute cooling degree days with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Temperature threshold. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    temperature_col : str, optional
        Column holding temperature values. If None, the first column in `ts_df` is
        used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily mean temperature before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("cooling_degree_days", "thresh")
    if freq is None:
        freq = _get_xclim_default("cooling_degree_days", "freq")

    # get temperature column
    temperature_col = _get_single_col(ts_df, temperature_col)

    # convert to xarray and resample as required by xclim index input
    tas_ts_da = _to_xarray_resampled(
        ts_df,
        temperature_col,
        temperature_unit,
        freq="D",
        agg="mean",
    )

    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(xci.cooling_degree_days(tas_ts_da, thresh=thresh, freq=freq))


def heating_degree_days(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    freq: str | None = None,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
):
    """Compute heating degree days with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Temperature threshold. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    temperature_col : str, optional
        Column holding temperature values. If None, the first column in `ts_df` is
        used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily mean temperature before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("heating_degree_days", "thresh")
    if freq is None:
        freq = _get_xclim_default("heating_degree_days", "freq")

    # get temperature column
    temperature_col = _get_single_col(ts_df, temperature_col)

    # convert to xarray and resample as required by xclim index input
    tas_ts_da = _to_xarray_resampled(
        ts_df,
        temperature_col,
        temperature_unit,
        freq="D",
        agg="mean",
    )

    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(xci.heating_degree_days(tas_ts_da, thresh=thresh, freq=freq))


def frost_days(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    freq: str | None = None,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
):
    """Compute frost days with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Temperature threshold. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    temperature_col : str, optional
        Column holding temperature values. If None, the first column in `ts_df` is
        used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily minimum temperature before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("frost_days", "thresh")
    if freq is None:
        freq = _get_xclim_default("frost_days", "freq")

    # get temperature column
    temperature_col = _get_single_col(ts_df, temperature_col)

    # convert to xarray and resample as required by xclim index input
    tas_ts_da = _to_xarray_resampled(
        ts_df,
        temperature_col,
        temperature_unit,
        freq="D",
        agg="min",
    )

    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(xci.frost_days(tas_ts_da, thresh=thresh, freq=freq))


def ice_days(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    freq: str | None = None,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
):
    """Compute ice days with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Temperature threshold. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    temperature_col : str, optional
        Column holding temperature values. If None, the first column in `ts_df` is
        used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily maximum temperature before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("ice_days", "thresh")
    if freq is None:
        freq = _get_xclim_default("ice_days", "freq")

    # get temperature column
    temperature_col = _get_single_col(ts_df, temperature_col)

    # convert to xarray and resample as required by xclim index input
    tas_ts_da = _to_xarray_resampled(
        ts_df,
        temperature_col,
        temperature_unit,
        freq="D",
        agg="max",
    )

    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(xci.ice_days(tas_ts_da, thresh=thresh, freq=freq))


def heat_index(
    ts_df: pd.DataFrame,
    *,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
    relative_humidity_col: str | None = None,
    relative_humidity_unit: str = "%",
):
    """Compute heat index with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    temperature_col : str, optional
        Column holding temperature values. If None, the default ECV name
        `settings.ECV_TEMPERATURE` is used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.
    relative_humidity_col : str, optional
        Column holding relative humidity values. If None, the default ECV name
        `settings.ECV_RELATIVE_HUMIDITY` is used.
    relative_humidity_unit : str, default "%"
        Units of the relative humidity values. Ignored when `ts_df` provides unit
        metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.
    """
    # get temperature column
    temperature_col = _get_col_or_default(temperature_col, settings.ECV_TEMPERATURE)
    # get relative humidity column
    relative_humidity_col = _get_col_or_default(
        relative_humidity_col, settings.ECV_RELATIVE_HUMIDITY
    )

    # convert to xarray
    tas_ts_da = _to_xarray(ts_df, temperature_col, temperature_unit)
    hurs_ts_da = _to_xarray(ts_df, relative_humidity_col, relative_humidity_unit)

    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(xci.heat_index(tas_ts_da, hurs_ts_da))


def hot_days(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    freq: str | None = None,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
):
    """Compute hot days with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Temperature threshold. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    temperature_col : str, optional
        Column holding temperature values. If None, the first column in `ts_df` is
        used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily maximum temperature before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("hot_days", "thresh")
    if freq is None:
        freq = _get_xclim_default("hot_days", "freq")

    # get temperature column
    temperature_col = _get_single_col(ts_df, temperature_col)

    # convert to xarray and resample as required by xclim index input
    ts_da = _to_xarray_resampled(
        ts_df,
        temperature_col,
        temperature_unit,
        freq="D",
        agg="max",
    )

    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(xci.hot_days(ts_da, thresh=thresh, freq=freq))


def hot_spell_frequency(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    window: int | None = None,
    freq: str | None = None,
    op: str | None = None,
    resample_before_rl: bool | None = None,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
):
    """Compute hot spell frequency with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Temperature threshold. If None, the xclim default is used.
    window : int, optional
        Minimum consecutive days for a spell. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    op : str, optional
        Comparison operator. If None, the xclim default is used.
    resample_before_rl : bool, optional
        Whether to resample before run length calculation. If None, the xclim
        default is used.
    temperature_col : str, optional
        Column holding temperature values. If None, the first column in `ts_df` is
        used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily maximum temperature before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("hot_spell_frequency", "thresh")
    if window is None:
        window = _get_xclim_default("hot_spell_frequency", "window")
    if freq is None:
        freq = _get_xclim_default("hot_spell_frequency", "freq")
    if op is None:
        op = _get_xclim_default("hot_spell_frequency", "op")
    if resample_before_rl is None:
        resample_before_rl = _get_xclim_default(
            "hot_spell_frequency", "resample_before_rl"
        )

    # get temperature column
    temperature_col = _get_single_col(ts_df, temperature_col)

    # convert to xarray and resample as required by xclim index input
    ts_da = _to_xarray_resampled(
        ts_df,
        temperature_col,
        temperature_unit,
        freq="D",
        agg="max",
    )

    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(
        xci.hot_spell_frequency(
            ts_da,
            thresh=thresh,
            window=window,
            freq=freq,
            op=op,
            resample_before_rl=resample_before_rl,
        )
    )


def hot_spell_total_length(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    window: int | None = None,
    freq: str | None = None,
    op: str | None = None,
    resample_before_rl: bool | None = None,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
):
    """Compute hot spell total length with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Temperature threshold. If None, the xclim default is used.
    window : int, optional
        Minimum consecutive days for a spell. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    op : str, optional
        Comparison operator. If None, the xclim default is used.
    resample_before_rl : bool, optional
        Whether to resample before run length calculation. If None, the xclim
        default is used.
    temperature_col : str, optional
        Column holding temperature values. If None, the first column in `ts_df` is
        used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily maximum temperature before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("hot_spell_total_length", "thresh")
    if window is None:
        window = _get_xclim_default("hot_spell_total_length", "window")
    if freq is None:
        freq = _get_xclim_default("hot_spell_total_length", "freq")
    if op is None:
        op = _get_xclim_default("hot_spell_total_length", "op")
    if resample_before_rl is None:
        resample_before_rl = _get_xclim_default(
            "hot_spell_total_length", "resample_before_rl"
        )

    # get temperature column
    temperature_col = _get_single_col(ts_df, temperature_col)

    # convert to xarray and resample as required by xclim index input
    ts_da = _to_xarray_resampled(
        ts_df,
        temperature_col,
        temperature_unit,
        freq="D",
        agg="max",
    )

    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(
        xci.hot_spell_total_length(
            ts_da,
            thresh=thresh,
            window=window,
            freq=freq,
            op=op,
            resample_before_rl=resample_before_rl,
        )
    )


def humidex(
    ts_df: pd.DataFrame,
    *,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
    dew_point_temperature_col: str | None = None,
    dew_point_temperature_unit: str = "degC",
    relative_humidity_col: str | None = None,
    relative_humidity_unit: str = "%",
):
    """Compute humidex with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    temperature_col : str, optional
        Column holding temperature values. If None, the default ECV name
        `settings.ECV_TEMPERATURE` is used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.
    dew_point_temperature_col : str, optional
        Column holding dew point temperature values. If None, the default ECV name
        `settings.ECV_DEW_POINT_TEMPERATURE` is used.
    dew_point_temperature_unit : str, default "degC"
        Units of the dew point temperature values. Ignored when `ts_df` provides unit
        metadata.
    relative_humidity_col : str, optional
        Column holding relative humidity values. If None, the default ECV name
        `settings.ECV_RELATIVE_HUMIDITY` is used.
    relative_humidity_unit : str, default "%"
        Units of the relative humidity values. Ignored when `ts_df` provides unit
        metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    If the dew point column is not available, relative humidity is used instead.
    """
    # get temperature column
    temperature_col = _get_col_or_default(temperature_col, settings.ECV_TEMPERATURE)
    # get dew point temperature column
    dew_point_temperature_col = _get_col_or_default(
        dew_point_temperature_col, settings.ECV_DEW_POINT_TEMPERATURE
    )
    # get relative humidity column
    relative_humidity_col = _get_col_or_default(
        relative_humidity_col, settings.ECV_RELATIVE_HUMIDITY
    )

    # convert to xarray
    tas_ts_da = _to_xarray(ts_df, temperature_col, temperature_unit)
    if dew_point_temperature_col in ts_df.columns:
        tdps_ts_da = _to_xarray(
            ts_df, dew_point_temperature_col, dew_point_temperature_unit
        )
        # set relative humidity as None
        hurs_ts_da = None
    else:
        # set dew point temperature as None
        tdps_ts_da = None
        # only transform relative humidity to xarray if dew point temperature is not
        # provided
        hurs_ts_da = _to_xarray(ts_df, relative_humidity_col, relative_humidity_unit)
    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(xci.humidex(tas_ts_da, tdps=tdps_ts_da, hurs=hurs_ts_da))


def daily_temperature_range(
    ts_df: pd.DataFrame,
    *,
    freq: str | None = None,
    op: str | None = None,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
):
    """Compute daily temperature range with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    op : str, optional
        Aggregation operator for the temperature range. If None, the xclim default is
        used.
    temperature_col : str, optional
        Column holding temperature values. If None, the first column in `ts_df` is
        used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily minimum and maximum temperature before computing the index.
    """
    if freq is None:
        freq = _get_xclim_default("daily_temperature_range", "freq")
    if op is None:
        op = _get_xclim_default("daily_temperature_range", "op")

    # get temperature column
    temperature_col = _get_single_col(ts_df, temperature_col)

    # convert to xarray and resample as required by xclim index input
    tasmin_ts_da = _to_xarray_resampled(
        ts_df,
        temperature_col,
        temperature_unit,
        freq="D",
        agg="min",
    )
    tasmax_ts_da = _to_xarray_resampled(
        ts_df,
        temperature_col,
        temperature_unit,
        freq="D",
        agg="max",
    )

    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(
        xci.daily_temperature_range(tasmin_ts_da, tasmax_ts_da, freq=freq, op=op)
    )


def prcptot(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    freq: str | None = None,
    precipitation_col: str | None = None,
    precipitation_unit: str = "mm/day",
):
    """Compute total precipitation with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Precipitation threshold. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    precipitation_col : str, optional
        Column holding precipitation values. If None, the default ECV name
        `settings.ECV_PRECIPITATION` is used.
    precipitation_unit : str, default "mm/day"
        Units of the precipitation values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily total precipitation before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("prcptot", "thresh")
    if freq is None:
        freq = _get_xclim_default("prcptot", "freq")

    precipitation_col = _get_col_or_default(
        precipitation_col, settings.ECV_PRECIPITATION
    )

    pr_ts_da = _to_xarray_resampled(
        ts_df,
        precipitation_col,
        precipitation_unit,
        freq="D",
        agg="sum",
    )

    return _to_pandas(xci.prcptot(pr_ts_da, thresh=thresh, freq=freq))


def wetdays(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    freq: str | None = None,
    op: str | None = None,
    precipitation_col: str | None = None,
    precipitation_unit: str = "mm/day",
):
    """Compute wet days with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Precipitation threshold. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    op : str, optional
        Comparison operator. If None, the xclim default is used.
    precipitation_col : str, optional
        Column holding precipitation values. If None, the default ECV name
        `settings.ECV_PRECIPITATION` is used.
    precipitation_unit : str, default "mm/day"
        Units of the precipitation values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily total precipitation before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("wetdays", "thresh")
    if freq is None:
        freq = _get_xclim_default("wetdays", "freq")
    if op is None:
        op = _get_xclim_default("wetdays", "op")

    precipitation_col = _get_col_or_default(
        precipitation_col, settings.ECV_PRECIPITATION
    )

    pr_ts_da = _to_xarray_resampled(
        ts_df,
        precipitation_col,
        precipitation_unit,
        freq="D",
        agg="sum",
    )

    return _to_pandas(xci.wetdays(pr_ts_da, thresh=thresh, freq=freq, op=op))


def dry_days(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    freq: str | None = None,
    op: str | None = None,
    precipitation_col: str | None = None,
    precipitation_unit: str = "mm/day",
):
    """Compute dry days with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Precipitation threshold. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    op : str, optional
        Comparison operator. If None, the xclim default is used.
    precipitation_col : str, optional
        Column holding precipitation values. If None, the default ECV name
        `settings.ECV_PRECIPITATION` is used.
    precipitation_unit : str, default "mm/day"
        Units of the precipitation values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily total precipitation before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("dry_days", "thresh")
    if freq is None:
        freq = _get_xclim_default("dry_days", "freq")
    if op is None:
        op = _get_xclim_default("dry_days", "op")

    precipitation_col = _get_col_or_default(
        precipitation_col, settings.ECV_PRECIPITATION
    )

    pr_ts_da = _to_xarray_resampled(
        ts_df,
        precipitation_col,
        precipitation_unit,
        freq="D",
        agg="sum",
    )

    return _to_pandas(xci.dry_days(pr_ts_da, thresh=thresh, freq=freq, op=op))


def max_1day_precipitation_amount(
    ts_df: pd.DataFrame,
    *,
    freq: str | None = None,
    precipitation_col: str | None = None,
    precipitation_unit: str = "mm/day",
):
    """Compute maximum 1-day precipitation amount with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    precipitation_col : str, optional
        Column holding precipitation values. If None, the default ECV name
        `settings.ECV_PRECIPITATION` is used.
    precipitation_unit : str, default "mm/day"
        Units of the precipitation values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily total precipitation before computing the index.
    """
    if freq is None:
        freq = _get_xclim_default("max_1day_precipitation_amount", "freq")

    precipitation_col = _get_col_or_default(
        precipitation_col, settings.ECV_PRECIPITATION
    )

    pr_ts_da = _to_xarray_resampled(
        ts_df,
        precipitation_col,
        precipitation_unit,
        freq="D",
        agg="sum",
    )

    return _to_pandas(xci.max_1day_precipitation_amount(pr_ts_da, freq=freq))


def max_n_day_precipitation_amount(
    ts_df: pd.DataFrame,
    *,
    window: int | None = None,
    freq: str | None = None,
    precipitation_col: str | None = None,
    precipitation_unit: str = "mm/day",
):
    """Compute maximum n-day precipitation amount with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    window : int, optional
        Rolling window (in days). If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    precipitation_col : str, optional
        Column holding precipitation values. If None, the default ECV name
        `settings.ECV_PRECIPITATION` is used.
    precipitation_unit : str, default "mm/day"
        Units of the precipitation values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily total precipitation before computing the index.
    """
    if window is None:
        window = _get_xclim_default("max_n_day_precipitation_amount", "window")
    if freq is None:
        freq = _get_xclim_default("max_n_day_precipitation_amount", "freq")

    precipitation_col = _get_col_or_default(
        precipitation_col, settings.ECV_PRECIPITATION
    )

    pr_ts_da = _to_xarray_resampled(
        ts_df,
        precipitation_col,
        precipitation_unit,
        freq="D",
        agg="sum",
    )

    return _to_pandas(
        xci.max_n_day_precipitation_amount(pr_ts_da, window=window, freq=freq)
    )


def sfc_wind_mean(
    ts_df: pd.DataFrame,
    *,
    freq: str | None = None,
    wind_speed_col: str | None = None,
    wind_speed_unit: str = "m s-1",
):
    """Compute mean wind speed with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    wind_speed_col : str, optional
        Column holding wind speed values. If None, the default ECV name
        `settings.ECV_WIND_SPEED` is used.
    wind_speed_unit : str, default "m s-1"
        Units of the wind speed values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily mean wind speed before computing the index.
    """
    if freq is None:
        freq = _get_xclim_default("sfcWind_mean", "freq")

    wind_speed_col = _get_col_or_default(wind_speed_col, settings.ECV_WIND_SPEED)

    sfcwind_ts_da = _to_xarray_resampled(
        ts_df,
        wind_speed_col,
        wind_speed_unit,
        freq="D",
        agg="mean",
    )

    return _to_pandas(xci.sfcWind_mean(sfcwind_ts_da, freq=freq))


def sfc_wind_max(
    ts_df: pd.DataFrame,
    *,
    freq: str | None = None,
    wind_speed_col: str | None = None,
    wind_speed_unit: str = "m s-1",
):
    """Compute maximum wind speed with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    wind_speed_col : str, optional
        Column holding wind speed values. If None, the default ECV name
        `settings.ECV_WIND_SPEED` is used.
    wind_speed_unit : str, default "m s-1"
        Units of the wind speed values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily mean wind speed before computing the index.
    """
    if freq is None:
        freq = _get_xclim_default("sfcWind_max", "freq")

    wind_speed_col = _get_col_or_default(wind_speed_col, settings.ECV_WIND_SPEED)

    sfcwind_ts_da = _to_xarray_resampled(
        ts_df,
        wind_speed_col,
        wind_speed_unit,
        freq="D",
        agg="mean",
    )

    return _to_pandas(xci.sfcWind_max(sfcwind_ts_da, freq=freq))


def sfc_wind_min(
    ts_df: pd.DataFrame,
    *,
    freq: str | None = None,
    wind_speed_col: str | None = None,
    wind_speed_unit: str = "m s-1",
):
    """Compute minimum wind speed with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    wind_speed_col : str, optional
        Column holding wind speed values. If None, the default ECV name
        `settings.ECV_WIND_SPEED` is used.
    wind_speed_unit : str, default "m s-1"
        Units of the wind speed values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily mean wind speed before computing the index.
    """
    if freq is None:
        freq = _get_xclim_default("sfcWind_min", "freq")

    wind_speed_col = _get_col_or_default(wind_speed_col, settings.ECV_WIND_SPEED)

    sfcwind_ts_da = _to_xarray_resampled(
        ts_df,
        wind_speed_col,
        wind_speed_unit,
        freq="D",
        agg="mean",
    )

    return _to_pandas(xci.sfcWind_min(sfcwind_ts_da, freq=freq))


def windy_days(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    freq: str | None = None,
    wind_speed_col: str | None = None,
    wind_speed_unit: str = "m s-1",
):
    """Compute windy days with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Wind speed threshold. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    wind_speed_col : str, optional
        Column holding wind speed values. If None, the default ECV name
        `settings.ECV_WIND_SPEED` is used.
    wind_speed_unit : str, default "m s-1"
        Units of the wind speed values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily mean wind speed before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("windy_days", "thresh")
    if freq is None:
        freq = _get_xclim_default("windy_days", "freq")

    wind_speed_col = _get_col_or_default(wind_speed_col, settings.ECV_WIND_SPEED)

    sfcwind_ts_da = _to_xarray_resampled(
        ts_df,
        wind_speed_col,
        wind_speed_unit,
        freq="D",
        agg="mean",
    )

    return _to_pandas(xci.windy_days(sfcwind_ts_da, thresh=thresh, freq=freq))


def tn_days_above(
    ts_df: pd.DataFrame,
    *,
    thresh: str | None = None,
    freq: str | None = None,
    op: str | None = None,
    temperature_col: str | None = None,
    temperature_unit: str = "degC",
):
    """Compute number of days above a minimum temperature threshold with xclim.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    thresh : str, optional
        Temperature threshold. If None, the xclim default is used.
    freq : str, optional
        Resampling frequency for the index output. If None, the xclim default is used.
    op : str, optional
        Comparison operator. If None, the xclim default is used.
    temperature_col : str, optional
        Column holding temperature values. If None, the first column in `ts_df` is
        used.
    temperature_unit : str, default "degC"
        Units of the temperature values. Ignored when `ts_df` provides unit metadata.

    Returns
    -------
    pandas.DataFrame
        Data frame with time as index and stations as columns.

    Notes
    -----
    Uses daily minimum temperature before computing the index.
    """
    if thresh is None:
        thresh = _get_xclim_default("tn_days_above", "thresh")
    if freq is None:
        freq = _get_xclim_default("tn_days_above", "freq")
    if op is None:
        op = _get_xclim_default("tn_days_above", "op")

    # get temperature column
    temperature_col = _get_single_col(ts_df, temperature_col)

    # convert to xarray and resample as required by xclim index input
    ts_da = _to_xarray_resampled(
        ts_df,
        temperature_col,
        temperature_unit,
        freq="D",
        agg="min",
    )

    # compute index, transpose to have time as index and station ids as columns
    return _to_pandas(xci.tn_days_above(ts_da, thresh=thresh, freq=freq, op=op))

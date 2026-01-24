"""Unit support with pint and pint-pandas."""

from collections.abc import Mapping

import pandas as pd
import pint_pandas
from pint import UnitRegistry

_UNIT_REGISTRY: UnitRegistry | None = None


def _get_unit_registry() -> UnitRegistry:
    global _UNIT_REGISTRY
    if _UNIT_REGISTRY is None:
        _UNIT_REGISTRY = UnitRegistry()
    return _UNIT_REGISTRY


def attach_units(ts_df: pd.DataFrame, units_map: Mapping) -> pd.DataFrame:
    """Attach units metadata to a time series data frame.

    Parameters
    ----------
    ts_df : pd.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    units_map : Mapping
        Mapping from column names to unit strings.

    Returns
    -------
    pd.DataFrame
        Copy of the input data frame with units metadata in ``attrs["units"]``.
    """
    ts_df = ts_df.copy()
    ts_df.attrs = ts_df.attrs.copy()
    ts_df.attrs["units"] = dict(units_map)
    return ts_df


def _convert_series_units(series: pd.Series, from_unit: str, to_unit: str) -> pd.Series:
    if from_unit == to_unit:
        return series
    ureg = _get_unit_registry()
    if pint_pandas is not None:
        dtype = f"pint[{from_unit}]"
        converted = series.astype(dtype).pint.to(to_unit)
        return pd.Series(converted.pint.magnitude, index=series.index, name=series.name)
    quantity = series.to_numpy(dtype=float) * ureg(from_unit)
    return pd.Series(
        quantity.to(to_unit).magnitude, index=series.index, name=series.name
    )


def convert_units(
    ts_df: pd.DataFrame,
    target_units: Mapping,
    *,
    source_units: Mapping | None = None,
    strict: bool = False,
) -> pd.DataFrame:
    """Convert data frame columns to target units.

    Parameters
    ----------
    ts_df : pd.DataFrame
        Long form data frame with a time series of measurements (second-level index) at
        each station (first-level index) for each variable (column).
    target_units : Mapping
        Mapping from column names to target unit strings.
    source_units : Mapping, optional
        Mapping from column names to source unit strings. Used only when
        ``ts_df.attrs["units"]`` is missing or empty.
    strict : bool, optional
        Whether to raise when a column is missing unit information.

    Returns
    -------
    pd.DataFrame
        Data frame converted to the target units with updated units metadata.

    Raises
    ------
    ValueError
        If no source units are available or if ``strict`` is True and a unit is
        missing for a column.
    """
    attrs_units = ts_df.attrs.get("units")
    if isinstance(attrs_units, Mapping) and attrs_units:
        source_units_map = attrs_units
    elif source_units is not None:
        source_units_map = source_units
    else:
        raise ValueError(
            "Missing source units: provide `source_units` or attach units metadata to"
            ' `ts_df.attrs["units"]`.'
        )
    ts_df = ts_df.copy()
    for col in ts_df.columns:
        from_unit = source_units_map.get(col)
        to_unit = target_units.get(col)
        if from_unit is None or to_unit is None:
            if strict:
                raise ValueError(f"Missing unit for column {col!r}.")
            continue
        if from_unit == to_unit:
            continue
        ts_df[col] = _convert_series_units(ts_df[col], from_unit, to_unit)
    ts_df.attrs = ts_df.attrs.copy()
    ts_df.attrs["units"] = dict(target_units)
    return ts_df

"""Quality control for CWS data.

Based on Meier et al., 2017 (https://doi.org/10.1016/j.uclim.2017.01.006) and Napoly et
al., 2018 (https://doi.org/10.3389/feart.2018.00118).
"""

from collections.abc import Callable, Sequence

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from statsmodels.tsa import ar_model, stattools

from meteora import settings, utils


def comparison_lineplot(
    ts_df: pd.DataFrame,
    discard_stations: Sequence,
    *,
    label_discarded: str = "discarded",
    label_kept: str = "kept",
    individual_discard_lines: bool = False,
    ax: mpl.axes.Axes = None,
):
    """Plot time series for discarded and kept stations separately.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Wide time series data frame with stations as columns and time as index.
    discard_stations : list-like
        Station ids to discard.
    label_discarded, label_kept : str, default "discarded", "kept"
        Label for discarded and kept stations, respectively.
    individual_discard_lines : bool, default False
        Plot discarded stations as individual lines (rather than line with mean and
        confidence intervals).
    ax : matplotlib.axes.Axes, default None
        Axes object to plot on. If None, a new figure is created.

    Returns
    -------
    ax : matplotlib.axes.Axes
        Axes object with the plot.
    """
    data = pd.concat(
        [
            _ts_df.reset_index()
            .melt(value_name="temperature", id_vars="time")
            .assign(label=label)
            for _ts_df, label in zip(
                [
                    ts_df[discard_stations],
                    ts_df.drop(columns=discard_stations, errors="ignore"),
                ],
                [label_discarded, label_kept],
            )
        ],
        ignore_index=True,
    )
    if ax is None:
        _, ax = plt.subplots()
    if individual_discard_lines:
        # to avoid warnings about matplotlib converters
        pd.plotting.register_matplotlib_converters()
        sns.lineplot(
            data[data["label"] == label_kept],
            x="time",
            y="temperature",
            hue="label",
            ax=ax,
        )
        data[data["label"] == label_discarded].set_index("time").rename(
            columns={"temperature": label_discarded}
        ).plot(ax=ax)
    else:
        sns.lineplot(
            data,
            x="time",
            y="temperature",
            hue="label",
            ax=ax,
        )
        ax.tick_params(axis="x", labelrotation=45)
    return ax


def get_mislocated_stations(station_gser: gpd.GeoSeries) -> list:
    """Get mislocated stations.

    When multiple stations share the same location, it is likely due to an incorrect
    set up that led to automatic location assignment based on the IP address of the
    wireless network.

    Parameters
    ----------
    station_gser : geopandas.GeoSeries
        Geoseries of station locations (points).

    Returns
    -------
    mislocated_stations : list
        List of station ids considered mislocated.
    """
    mislocated_station_ser = station_gser.duplicated(keep=False)
    return list(mislocated_station_ser[mislocated_station_ser].index)


# function to filter stations depending on the proportion of available valid
# measurements
def get_unreliable_stations(
    ts_df: pd.DataFrame, *, unreliable_threshold: float | None = None
) -> list:
    """Get stations with a high proportion of non-valid measurements.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    unreliable_threshold : numeric, optional
        Proportion of non-valid measurements after which a station is considered
        unreliable. If None, the value from `settings.UNRELIABLE_THRESHOLD` is used.

    Returns
    -------
    unreliable_stations : list
        List of station ids considered unreliable.

    """
    if unreliable_threshold is None:
        unreliable_threshold = settings.UNRELIABLE_THRESHOLD

    unreliable_station_ser = (
        ts_df.isna().sum() / len(ts_df.index) > unreliable_threshold
    )
    return list(unreliable_station_ser[unreliable_station_ser].index)


def elevation_adjustment(
    ts_df: pd.DataFrame,
    station_elevation_ser: pd.Series,
    *,
    atmospheric_lapse_rate: float | None = None,
) -> pd.DataFrame:
    """Adjust temperature measurements based on station elevation.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    station_elevation_ser : pandas.Series, optional
        Series of station elevations, indexed by the station id. If provided, the
        series of measurements is adjusted to account for the elevation effect.
    atmospheric_lapse_rate : numeric, optional
        Atmospheric lapse rate (in unit of `ts_df` per unit of `elevation_station_ser`)
        to account for the elevation effect. Ignored if `elevation_station_ser` is not
        provided. If None, the value from `settings.ATMOSPHERIC_LAPSE_RATE` is used.

    Returns
    -------
    adjusted_ts_df : pandas.DataFrame
        Time series of adjusted measurements (rows) for each station (columns).

    """
    if atmospheric_lapse_rate is None:
        atmospheric_lapse_rate = settings.ATMOSPHERIC_LAPSE_RATE
    station_elevation_ser = station_elevation_ser[ts_df.columns]
    return ts_df + atmospheric_lapse_rate * (
        station_elevation_ser - station_elevation_ser.mean()
    )


def get_z_ts_df(
    ts_df: pd.DataFrame,
    center: str | Callable = "mean",
    divisor: str | Callable = "std",
) -> pd.DataFrame:
    """Get z-scores of the time series.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    center, divisor : str or callable, default "mean" and "std"
        Function to compute the center and divisor of the z-score. If a string, it is
        interpreted as the name of a method of the DataFrame (e.g. "mean", "median" or
        "std"). If a callable, it is passed to the `apply` method of `ts_df` along the
        "columns" axis (i.e. for each station).

    Returns
    -------
    z_ts_df : pandas.DataFrame
        Z-scores of the time series (rows) for each station (columns).

    """
    if isinstance(center, str):
        center = getattr(ts_df, center)
        center_ser = center(axis="columns")
    else:
        center_ser = ts_df.apply(center, axis="columns")
    if isinstance(divisor, str):
        divisor = getattr(ts_df, divisor)
        divisor_ser = divisor(axis="columns")
    else:
        divisor_ser = ts_df.apply(divisor, axis="columns")

    return ts_df.sub(center_ser, axis="rows").div(divisor_ser, axis="rows")


def _outlier_from_z(
    z_ts: pd.Series | pd.DataFrame,
    *,
    lower_threshold: float | None = -3,
    upper_threshold: float | None = 3,
) -> pd.Series | pd.DataFrame:
    if lower_threshold is None and upper_threshold is None:
        raise ValueError(
            "Either `lower_threshold` or `upper_threshold` must be provided."
        )
    if isinstance(z_ts, pd.Series):
        outlier_ts = pd.Series(False, index=z_ts.index)
    elif isinstance(z_ts, pd.DataFrame):
        outlier_ts = pd.DataFrame(False, index=z_ts.index, columns=z_ts.columns)
    else:
        raise ValueError("`z_ts` must be either a pandas series or data frame")

    if lower_threshold is not None:
        outlier_ts |= z_ts.lt(lower_threshold)
    if upper_threshold is not None:
        outlier_ts |= z_ts.gt(upper_threshold)

    return outlier_ts


def get_outlier_ts_df(
    ts_df: pd.DataFrame,
    *,
    center: str | Callable = "mean",
    divisor: str | Callable = "std",
    lower_threshold: float | None = -3,
    upper_threshold: float | None = 3,
) -> pd.DataFrame:
    """Get boolean time series of outliers for each station.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    center, divisor : str or callable, default "mean" and "std"
        Function to compute the center and divisor of the z-score. If a string, it is
        interpreted as the name of a method of the DataFrame (e.g. "mean", "median" or
        "std"). If a callable, it is passed to the `apply` method of `ts_df` along the
        "columns" axis (i.e. for each station).
    lower_threshold, upper_threshold : numeric, optional
        Lower and upper z-score thresholds for each tail respectively. The default value
        of -3 and 3 respectively correspond to the three-sigma rule. If None, no outlier
        detection is done for the corresponding tail. At least one of the thresholds
        must be provided.

    Returns
    -------
    outlier_ts_df : pandas.DataFrame
        Time series of boolean values (rows) for each station (columns) representing
        whether the station observation at that time is considered an outlier.
    """
    z_ts_df = get_z_ts_df(ts_df, center=center, divisor=divisor)
    return _outlier_from_z(
        z_ts_df, lower_threshold=lower_threshold, upper_threshold=upper_threshold
    )


def _get_radiative_error_outlier_thresholds(
    ts_df: pd.DataFrame,
    *,
    lower_alpha: float | None = None,
    upper_alpha: float | None = None,
    distribution: str | None = None,
    shape_params: Sequence | None = None,
) -> tuple[float, float]:
    if lower_alpha is None:
        lower_alpha = settings.RADIATIVE_ERROR_LOWER_ALPHA
    if upper_alpha is None:
        upper_alpha = settings.RADIATIVE_ERROR_UPPER_ALPHA

    if distribution is None:
        if len(ts_df.columns) >= 100:
            # normal
            lower_z = stats.norm.ppf(lower_alpha)
            upper_z = stats.norm.ppf(upper_alpha)
        else:
            # t-distribution
            dof = len(ts_df.columns) - 1
            lower_z = stats.t.ppf(lower_alpha, dof)
            upper_z = stats.t.ppf(upper_alpha, dof)
    else:
        distribution = getattr(stats, distribution)
        lower_z = distribution.ppf(lower_alpha, *shape_params)
        upper_z = distribution.ppf(upper_alpha, *shape_params)

    return lower_z, upper_z


def _get_radiative_error_z_ts_df(
    ts_df: pd.DataFrame,
    *,
    center: str | Callable | None = None,
    divisor: str | Callable | None = None,
) -> pd.DataFrame:
    if center is None:
        center = settings.RADIATIVE_ERROR_Z_CENTER
    if divisor is None:
        divisor = settings.RADIATIVE_ERROR_Z_DIVISOR

    return get_z_ts_df(
        ts_df,
        center=center,
        divisor=divisor,
    )


def _get_radiative_error_outlier_ts_df(
    ts_df: pd.DataFrame,
    *,
    lower_alpha: float | None = None,
    upper_alpha: float | None = None,
    distribution: str | None = None,
    shape_params: Sequence | None = None,
    center: str | Callable | None = None,
    divisor: str | Callable | None = None,
) -> pd.DataFrame:
    lower_z, upper_z = _get_radiative_error_outlier_thresholds(
        ts_df,
        lower_alpha=lower_alpha,
        upper_alpha=upper_alpha,
        distribution=distribution,
        shape_params=shape_params,
    )
    z_ts_df = _get_radiative_error_z_ts_df(ts_df, center=center, divisor=divisor)
    return _outlier_from_z(z_ts_df, lower_threshold=lower_z, upper_threshold=upper_z)


def get_radiative_error_stations(
    ts_df: pd.DataFrame,
    *,
    lower_alpha: float | None = None,
    upper_alpha: float | None = None,
    max_prop_threshold: float | None = None,
    distribution: str | None = None,
    shape_params: Sequence | None = None,
    center: str | Callable | None = None,
    divisor: str | Callable | None = None,
) -> list:
    """Get stations showing systematic radiative errors.

    Measurements can show suspicious deviations from a normal distribution (based on
    a modified z-score using robust Qn variance estimators). Stations with high
    proportion of such measurements are likely set up in a sunlit location and
    therefore show systematic radiative errors.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    lower_alpha, upper_alpha : numeric, optional
        Threshold values (in proportion from 0 to 1) to determine outliers for the lower
        and upper tail respectively. If None, the respective values from
        `settings.RADIATIVE_ERROR_LOWER_ALPHA` and
        `settings.RADIATIVE_ERROR_UPPER_ALPHA` are used.
    max_prop_threshold : numeric, optional
        Maximum proportion (from 0 to 1) of outlier measurements after which the
        respective station may be flagged as faulty. If None, the value from
        `settings.RADIATIVE_ERROR_MAX_PROP_THRESHOLD` is used.
    distribution : str, optional
        Distribution to determine the lower and upper thresholds. Can be any continuous
        distribution from `scipy.stats` (e.g. "norm", "t", etc.). If None, the normal
        distribution is used when number of stations greater or equal than 100 and the
        t-distribution is used otherwise.
    shape_params : list-like, optional
        Shape parameters for the distribution, positionally passed to the `ppf` method
        of the distribution.
    center, divisor : str or callable, optional
        Function to compute the center and divisor of the z-score. If a string, it is
        interpreted as the name of a method of the DataFrame (e.g. "mean", "median" or
        "std"). If a callable, it is passed to the `apply` method of `ts_df` along the
        "columns" axis (i.e. for each station). If None, the default values from
        `settings.RADIATIVE_ERROR_Z_CENTER` and `settings.RADIATIVE_ERROR_Z_DIVISOR`
        are used.

    Returns
    -------
    radiative_error_stations : list
        List of station ids for stations showing systematic radiative errors.
    """
    if max_prop_threshold is None:
        max_prop_threshold = settings.RADIATIVE_ERROR_MAX_PROP_THRESHOLD

    outlier_ts_df = _get_radiative_error_outlier_ts_df(
        ts_df,
        lower_alpha=lower_alpha,
        upper_alpha=upper_alpha,
        distribution=distribution,
        shape_params=shape_params,
        center=center,
        divisor=divisor,
    )
    prop_outlier_ser = outlier_ts_df.sum() / len(ts_df.index)

    return list(prop_outlier_ser[prop_outlier_ser.gt(max_prop_threshold)].index)


def get_daily_peak_overheating_stations(
    ts_df: pd.DataFrame,
    *,
    lower_alpha: float | None = None,
    upper_alpha: float | None = None,
    distribution: str | None = None,
    shape_params: Sequence | None = None,
    center: str | Callable | None = None,
    divisor: str | Callable | None = None,
):
    """Get stations showing a consistent daily peak outlier."""
    lower_z, upper_z = _get_radiative_error_outlier_thresholds(
        ts_df,
        lower_alpha=lower_alpha,
        upper_alpha=upper_alpha,
        distribution=distribution,
        shape_params=shape_params,
    )
    z_ts_df = _get_radiative_error_z_ts_df(ts_df, center=center, divisor=divisor)
    # avoid statsmodels warnings
    z_ts_df.index = pd.DatetimeIndex(z_ts_df.index, z_ts_df.index.inferred_freq)

    # get lags depending on frequency
    freq_hours = pd.to_timedelta(z_ts_df.index.freq).total_seconds() / 3600
    # TODO: make the 3 and 48 hours an argument with default in settings
    ar_lags = int(3 / freq_hours)
    acf_lags = int(48 / freq_hours)
    target_lag = int(24 / freq_hours)

    def _test_has_peak(station_ts_ser: pd.Series) -> bool:
        model = ar_model.AutoReg(station_ts_ser.ffill().bfill(), lags=ar_lags).fit()
        resid_acf = stattools.acf(model.resid, nlags=acf_lags)
        # always discard first residual (perfect correlation)
        peak = resid_acf[1:].argmax() + 1
        if peak != target_lag:
            return False

        # TODO: support CIs other than 0.95 via Bartlett's
        if resid_acf[peak] > 1.96 / np.sqrt(len(station_ts_ser)):
            # there is a significant peak
            return True

    flat_z_ts_df = z_ts_df.stack()
    z_ts_df_hourly_gb = flat_z_ts_df.groupby(
        flat_z_ts_df.index.get_level_values("time").hour
    )

    # TODO: do we need to compte the center or is it guaranteed to be zero?
    # z_ts_df_hourly_center = z_ts_df_hourly_gb.median()
    # z_ts_df_hourly_divisor = z_ts_df_hourly_gb.apply(scale.qn_scale)
    if divisor is None:
        divisor = settings.RADIATIVE_ERROR_Z_DIVISOR
    if isinstance(divisor, str):
        divisor = getattr(z_ts_df_hourly_gb, divisor)
        divisor_ser = divisor()
    else:
        divisor_ser = z_ts_df_hourly_gb.apply(divisor)

    def _test_peak_overheating(station_ts_ser: pd.Series) -> float:
        hourly_mean_ser = station_ts_ser.groupby(station_ts_ser.index.hour).mean()
        peak_hour = hourly_mean_ser.argmax(skipna=True)
        # return (hourly_mean_ser[peak_hour] - center_ser[peak_hour]) / divisor_ser[
        #     peak_hour
        # ]
        return hourly_mean_ser[peak_hour] / divisor_ser[peak_hour]

    return list(
        z_ts_df.columns[
            z_ts_df.apply(_test_has_peak, axis="rows")
            & _outlier_from_z(
                z_ts_df.apply(_test_peak_overheating, axis="rows"),
                # lower_threshold=lower_z,
                upper_threshold=upper_z,
            )
        ]
    )


def get_indoor_stations(
    ts_df: pd.DataFrame, *, station_indoor_corr_threshold: float | None = None
) -> list:
    """Get indoor stations.

    Stations whose time series of measurements show low correlations with the
    spatial median time series are likely set up indoors.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    station_indoor_corr_threshold : numeric, optional
        Stations showing Pearson correlations (with the overall station median
        distribution) lower than this threshold are likely set up indoors. If None,
        the value from `settings.STATION_INDOOR_CORR_THRESHOLD` is used.

    Returns
    -------
    indoor_stations : list
        List of station ids for stations flagged as indoor.

    """
    if station_indoor_corr_threshold is None:
        station_indoor_corr_threshold = settings.STATION_INDOOR_CORR_THRESHOLD

    indoor_station_ser = (
        ts_df.corrwith(ts_df.median(axis="columns")) < station_indoor_corr_threshold
    )
    return list(indoor_station_ser[indoor_station_ser].index)


def full_qc(
    ts_df: pd.DataFrame,
    *,
    station_gdf: gpd.GeoDataFrame | None = None,
    unreliable_threshold: float | None = None,
    radiative_error_stations_kwargs: utils.KwargsType | None = None,
    daily_peak_overheating_stations_kwargs: utils.KwargsType | None = None,
    replace_outliers: bool = False,
    get_outliers_kwargs: utils.KwargsType | None = None,
    replacement_value: float | None = np.nan,
    station_indoor_corr_threshold: float | None = None,
    adjust_elevation: bool | None = None,
    station_elevation: pd.Series | str | None = None,
    atmospheric_lapse_rate: float | None = None,
) -> dict | tuple[pd.DataFrame, dict]:
    """Perform full quality control on the time series data.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    """
    qc_dict = {}
    # mislocated stations (optional)
    if station_gdf is not None:
        mislocated_stations = get_mislocated_stations(station_gdf["geometry"])
        ts_df = ts_df.drop(columns=mislocated_stations, errors="ignore")
        qc_dict["mislocated"] = mislocated_stations

    # unreliable stations
    unreliable_stations = get_unreliable_stations(
        ts_df, unreliable_threshold=unreliable_threshold
    )
    ts_df = ts_df.drop(columns=unreliable_stations, errors="ignore")
    qc_dict["unreliable"] = unreliable_stations

    # elevation adjustment (optional)
    if adjust_elevation or (adjust_elevation is None and station_elevation is not None):
        if isinstance(station_elevation, str):
            # `station_elevation` is a column of `station_gdf`
            station_elevation = station_gdf[station_elevation]
        # at this point `station_elevation` must be a series indexed by the station ids
        _ts_df = elevation_adjustment(
            ts_df, station_elevation, atmospheric_lapse_rate=atmospheric_lapse_rate
        )
    else:
        _ts_df = ts_df.copy()

    # systematic radiative error stations
    if radiative_error_stations_kwargs is None:
        radiative_error_stations_kwargs = {}
    radiative_error_stations = get_radiative_error_stations(
        _ts_df,
        **radiative_error_stations_kwargs,
    )
    _ts_df = _ts_df.drop(columns=radiative_error_stations, errors="ignore")
    qc_dict["radiative_error"] = radiative_error_stations

    # daily peak overheating stations
    if daily_peak_overheating_stations_kwargs is None:
        daily_peak_overheating_stations_kwargs = {}
    daily_peak_overheating_stations = get_daily_peak_overheating_stations(
        _ts_df, **daily_peak_overheating_stations_kwargs
    )
    _ts_df = _ts_df.drop(columns=daily_peak_overheating_stations, errors="ignore")
    qc_dict["daily_peak_overheating"] = daily_peak_overheating_stations

    # indoor stations
    indoor_stations = get_indoor_stations(
        _ts_df, station_indoor_corr_threshold=station_indoor_corr_threshold
    )
    _ts_df = _ts_df.drop(columns=indoor_stations, errors="ignore")
    qc_dict["indoor"] = indoor_stations

    # replace outliers
    if replace_outliers:
        if get_outliers_kwargs is None:
            get_outliers_kwargs = radiative_error_stations_kwargs.copy()
            _ = get_outliers_kwargs.pop("max_prop_threshold", None)
            outlier_ts_df = _get_radiative_error_outlier_ts_df(
                _ts_df,
                **get_outliers_kwargs,
            )
        else:
            outlier_ts_df = get_outlier_ts_df(_ts_df)

        # ACHTUNG: if the data has been adjusted for elevation, it is important to
        # return the original data (not the adjusted data) with the outliers replaced
        _ts_df = ts_df[_ts_df.columns].where(~outlier_ts_df, other=replacement_value)

        return _ts_df, qc_dict

    return qc_dict

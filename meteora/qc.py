"""Quality control for CWS data.

Based on Napoly et al., 2018 (https://doi.org/10.3389/feart.2018.00118)
"""

from collections.abc import Sequence

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy.stats import norm
from statsmodels.robust import scale

from meteora import settings


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


def get_outlier_stations(
    ts_df: pd.DataFrame,
    *,
    low_alpha: float | None = None,
    high_alpha: float | None = None,
    station_outlier_threshold: float | None = None,
) -> list:
    """Get outlier stations.

    Measurements can show suspicious deviations from a normal distribution (based on
    a modified z-score using robust Qn variance estimators). Stations with high
    proportion of such measurements can be related to radiative errors in non-shaded
    areas or other measurement errors.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    low_alpha, high_alpha : numeric, optional
        Values for the lower and upper tail respectively (in proportion from 0 to 1)
        that lead to the rejection of the null hypothesis (i.e., the corresponding
        measurement does not follow a normal distribution can be considered an
        outlier). If None, the respective values from `settings.OUTLIER_LOW_ALPHA`
        and `settings.OUTLIER_HIGH_ALPHA` are used.
    station_outlier_threshold : numeric, optional
        Maximum proportion (from 0 to 1) of outlier measurements after which the
        respective station may be flagged as faulty. If None, the value from
        `settings.STATION_OUTLIER_THRESHOLD` is used.

    Returns
    -------
    outlier_stations : list
        List of station ids for stations flagged as outlier.
    """
    # def z_score(x):
    #     try:
    #         return (x - x.median()) / scale.qn_scale(x.dropna())
    #     except:
    #         print(x)
    #         raise ValueError("error")

    if low_alpha is None:
        low_alpha = settings.OUTLIER_LOW_ALPHA
    if high_alpha is None:
        high_alpha = settings.OUTLIER_HIGH_ALPHA
    if station_outlier_threshold is None:
        station_outlier_threshold = settings.STATION_OUTLIER_THRESHOLD

    low_z = norm.ppf(low_alpha)
    high_z = norm.ppf(high_alpha)
    prop_outlier_ser = ts_df.sub(ts_df.median(axis="columns"), axis="rows").div(
        ts_df.apply(scale.qn_scale, axis="columns"), axis="rows"
    ).apply(lambda z: ~z.between(low_z, high_z, inclusive="neither")).sum() / len(
        ts_df.index
    )
    outlier_station_ser = prop_outlier_ser > station_outlier_threshold
    return list(outlier_station_ser[outlier_station_ser].index)


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

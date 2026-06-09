"""Quality control for CWS data.

Based on Napoly et al., 2018 (https://doi.org/10.3389/feart.2018.00118)
"""

import inspect
import warnings
from collections.abc import Callable, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.robust import scale

from meteora import settings


def flag_mislocated(
    ts_df: pd.DataFrame, *, station_gser: gpd.GeoSeries | None = None
) -> tuple[pd.DataFrame, list]:
    """Flag mislocated stations.

    When multiple stations share the same location, it is likely due to an incorrect
    set up that led to automatic location assignment based on the IP address of the
    wireless network.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns); returned
        unchanged (this step flags stations purely from their geometry).
    station_gser : geopandas.GeoSeries, optional
        Geoseries of station locations (points). If None, the step is skipped (with a
        warning) and no station is flagged.

    Returns
    -------
    ts_df, mislocated_stations : pandas.DataFrame, list
        The (unchanged) time series data frame and the list of station ids considered
        mislocated.
    """
    if station_gser is None:
        warnings.warn(
            "Skipping `flag_mislocated`: no station geometry was provided.",
            stacklevel=2,
        )
        return ts_df, []
    mislocated_station_ser = station_gser.duplicated(keep=False)
    return ts_df, list(mislocated_station_ser[mislocated_station_ser].index)


# function to filter stations depending on the proportion of available valid
# measurements
def flag_unreliable(
    ts_df: pd.DataFrame,
    *,
    unreliable_threshold: float | None = None,
) -> tuple[pd.DataFrame, list]:
    """Flag stations with a high proportion of non-valid measurements.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    unreliable_threshold : numeric, optional
        Proportion of non-valid measurements after which a station is considered
        unreliable. If None, the value from `settings.UNRELIABLE_THRESHOLD` is used.

    Returns
    -------
    ts_df, unreliable_stations : pandas.DataFrame, list
        The (unchanged) time series data frame and the list of station ids considered
        unreliable.

    """
    if unreliable_threshold is None:
        unreliable_threshold = settings.UNRELIABLE_THRESHOLD

    unreliable_station_ser = (
        ts_df.isna().sum() / len(ts_df.index) > unreliable_threshold
    )
    return ts_df, list(unreliable_station_ser[unreliable_station_ser].index)


def adjust_elevation(
    ts_df: pd.DataFrame,
    *,
    station_elevation_ser: pd.Series | None = None,
    atmospheric_lapse_rate: float | None = None,
) -> tuple[pd.DataFrame, list]:
    """Adjust temperature measurements based on station elevation.

    Unlike the other (station-discarding) QC steps, this one *transforms* the time
    series and discards no station (its discard list is always empty).

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    station_elevation_ser : pandas.Series, optional
        Series of station elevations, indexed by the station id. If None, the step is
        skipped and `ts_df` is returned unchanged.
    atmospheric_lapse_rate : numeric, optional
        Atmospheric lapse rate (in unit of `ts_df` per unit of `station_elevation_ser`)
        to account for the elevation effect. If None, the value from
        `settings.ATMOSPHERIC_LAPSE_RATE` is used.

    Returns
    -------
    adjusted_ts_df, discarded : pandas.DataFrame, list
        The elevation-adjusted time series data frame and an (always empty) discard
        list.

    """
    if station_elevation_ser is None:
        return ts_df, []
    if atmospheric_lapse_rate is None:
        atmospheric_lapse_rate = settings.ATMOSPHERIC_LAPSE_RATE
    station_elevation_ser = station_elevation_ser[ts_df.columns]
    return (
        ts_df
        + atmospheric_lapse_rate
        * (station_elevation_ser - station_elevation_ser.mean()),
        [],
    )


def _outlier_mask(
    ts_df: pd.DataFrame,
    low_alpha: float | None = None,
    high_alpha: float | None = None,
) -> pd.DataFrame:
    """Boolean mask flagging individual measurements as outliers.

    A measurement is an outlier when its modified z-score - based on the per-time-step
    (cross-station) median and Qn scale estimator - falls outside the central interval
    delimited by the `low_alpha` and `high_alpha` tails of a normal distribution. Shared
    by `flag_outliers` (which aggregates it per station) and `mask_outliers` (which sets
    the flagged values to NaN).

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    low_alpha, high_alpha : numeric, optional
        Lower and upper tail proportions (from 0 to 1) beyond which a measurement is
        flagged as an outlier. If None, the respective values from
        `settings.OUTLIER_LOW_ALPHA` and `settings.OUTLIER_HIGH_ALPHA` are used.

    Returns
    -------
    outlier_df : pandas.DataFrame
        Boolean data frame (same shape as `ts_df`), True where the measurement is an
        outlier.
    """
    if low_alpha is None:
        low_alpha = settings.OUTLIER_LOW_ALPHA
    if high_alpha is None:
        high_alpha = settings.OUTLIER_HIGH_ALPHA
    low_z = norm.ppf(low_alpha)
    high_z = norm.ppf(high_alpha)
    return (
        ts_df.sub(ts_df.median(axis="columns"), axis="rows")
        .div(ts_df.apply(scale.qn_scale, axis="columns"), axis="rows")
        .apply(lambda z: ~z.between(low_z, high_z, inclusive="neither"))
    )


def flag_outliers(
    ts_df: pd.DataFrame,
    *,
    low_alpha: float | None = None,
    high_alpha: float | None = None,
    station_outlier_threshold: float | None = None,
) -> tuple[pd.DataFrame, list]:
    """Flag outlier stations.

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
    ts_df, outlier_stations : pandas.DataFrame, list
        The (unchanged) time series data frame and the list of station ids flagged as
        outlier.
    """
    if station_outlier_threshold is None:
        station_outlier_threshold = settings.STATION_OUTLIER_THRESHOLD
    prop_outlier_ser = _outlier_mask(ts_df, low_alpha, high_alpha).sum() / len(
        ts_df.index
    )
    outlier_station_ser = prop_outlier_ser > station_outlier_threshold
    return ts_df, list(outlier_station_ser[outlier_station_ser].index)


def mask_outliers(
    ts_df: pd.DataFrame,
    *,
    low_alpha: float | None = None,
    high_alpha: float | None = None,
) -> tuple[pd.DataFrame, list]:
    """Mask (set to NaN) individual outlier measurements.

    Unlike `flag_outliers`, which discards whole stations, this step replaces the
    individual measurements flagged as outliers (by the same modified z-score, see
    `_outlier_mask`) with NaN, leaving the rest untouched and discarding no station. It
    therefore *transforms* the time series rather than flagging stations, closer to the
    m2 level of CrowdQC+ (Fenner et al., 2021), which flags values rather than stations.
    It is deliberately *not* part of `settings.DEFAULT_QC_STEPS`.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    low_alpha, high_alpha : numeric, optional
        Lower and upper tail proportions (from 0 to 1) beyond which a measurement is
        masked. If None, the respective values from `settings.OUTLIER_LOW_ALPHA` and
        `settings.OUTLIER_HIGH_ALPHA` are used.

    Returns
    -------
    masked_ts_df, discarded : pandas.DataFrame, list
        The time series data frame with the outlier measurements set to NaN, and an
        (always empty) discard list.
    """
    return ts_df.mask(_outlier_mask(ts_df, low_alpha, high_alpha)), []


def flag_indoor(
    ts_df: pd.DataFrame,
    *,
    station_indoor_corr_threshold: float | None = None,
) -> tuple[pd.DataFrame, list]:
    """Flag indoor stations.

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
    ts_df, indoor_stations : pandas.DataFrame, list
        The (unchanged) time series data frame and the list of station ids flagged as
        indoor.

    """
    if station_indoor_corr_threshold is None:
        station_indoor_corr_threshold = settings.STATION_INDOOR_CORR_THRESHOLD

    indoor_station_ser = (
        ts_df.corrwith(ts_df.median(axis="columns")) < station_indoor_corr_threshold
    )
    return ts_df, list(indoor_station_ser[indoor_station_ser].index)


def _qn_row(row: np.ndarray) -> float:
    """Qn scale estimator of a row, ignoring non-valid values."""
    vals = row[~np.isnan(row)]
    if vals.size < 2:
        return np.nan
    return scale.qn_scale(vals)


# normalization constant of the Qn estimator (consistency at the normal distribution),
# matching `statsmodels.robust.scale.qn_scale`
_QN_C = 1.0 / (np.sqrt(2) * norm.ppf(5 / 8))


def _qn_rows(arr: np.ndarray) -> np.ndarray:
    """Row-wise Qn scale estimator, ignoring non-valid (NaN) values per row.

    Vectorized equivalent of applying `statsmodels.robust.scale.qn_scale` to each row
    (after dropping NaNs), returning NaN for rows with fewer than two valid values. For
    a row with ``n`` valid values the estimate is ``c * d_(k)``, the ``k``-th smallest
    of the ``i < j`` pairwise absolute differences, with ``k = h * (h - 1) / 2``,
    ``h = n // 2 + 1`` and ``c = _QN_C`` - the exact definition used by `qn_scale`, but
    computed for all rows at once instead of one (slow) Python call per row.

    Parameters
    ----------
    arr : numpy.ndarray
        Two-dimensional array of shape ``(n_rows, n_cols)``.

    Returns
    -------
    qn : numpy.ndarray
        One-dimensional array of length ``n_rows`` with the per-row Qn estimate.
    """
    arr = np.asarray(arr, dtype=float)
    n_rows, n_cols = arr.shape
    qn = np.full(n_rows, np.nan)
    if n_cols < 2:
        return qn
    # i < j pairwise absolute differences per row; a difference involving a NaN value is
    # set to +inf so it sorts last and is never picked as a (valid) k-th order statistic
    i, j = np.triu_indices(n_cols, k=1)
    diffs = np.abs(arr[:, i] - arr[:, j])
    n_valid = np.isfinite(arr).sum(axis=1)
    diffs = np.where(np.isnan(diffs), np.inf, diffs)
    h = n_valid // 2 + 1
    k = h * (h - 1) // 2
    rows = np.flatnonzero(n_valid >= 2)
    if rows.size:
        # only the k-th smallest (valid) difference per row is needed, so partition
        # rather than fully sort; passing every distinct k-th position lets us read each
        # row's order statistic directly
        kth = k[rows] - 1
        parted = np.partition(diffs[rows], np.unique(kth), axis=1)
        qn[rows] = _QN_C * parted[np.arange(rows.size), kth]
    return qn


def flag_buddies(
    ts_df: pd.DataFrame,
    *,
    station_gser: gpd.GeoSeries | None = None,
    buddy_radius: float | None = None,
    buddy_min_n: int | None = None,
    low_alpha: float | None = None,
    high_alpha: float | None = None,
    station_outlier_threshold: float | None = None,
    keep_isolated: bool = False,
) -> tuple[pd.DataFrame, list]:
    """Spatial buddy check.

    Outlier detection within the neighbourhood ("buddies") of each station, intended
    to catch faulty values - primarily single unrealistically high values due to
    radiative errors - that remain after the station-wise checks. For each station,
    the buddies are the stations within `buddy_radius`; at each time step the median
    and Qn scale estimator (a robust alternative to the standard deviation) are
    computed across the buddies (excluding the checked station), and a modified
    z-score is derived analogously to `flag_outliers`. A station is flagged as
    a buddy outlier when the proportion of its time steps with an outlier z-score
    exceeds `station_outlier_threshold`. Adapted from the m5 level of CrowdQC+
    (Fenner et al., 2021, https://doi.org/10.3389/feart.2021.720747); unlike the
    original, this check neither corrects for the atmospheric lapse rate (this is
    handled separately by `adjust_elevation`) nor flags individual values - only
    whole stations.

    Parameters
    ----------
    ts_df : pandas.DataFrame
        Time series of measurements (rows) for each station (columns).
    station_gser : geopandas.GeoSeries
        Geoseries of station locations (points), indexed by the station id. It is
        (re)projected to a metric CRS to compute the neighbourhoods, so `buddy_radius`
        is interpreted in meters. If None, the step is skipped (with a warning) and no
        station is flagged.
    buddy_radius : numeric, optional
        Radius (in meters) within which neighbouring stations are considered buddies.
        If None, the value from `settings.BUDDY_RADIUS` is used.
    buddy_min_n : int, optional
        Minimum number of buddies with valid data required to check a station. Stations
        with fewer buddies are flagged as isolated rather than evaluated. If None, the
        value from `settings.BUDDY_MIN_N` is used.
    low_alpha, high_alpha : numeric, optional
        Values for the lower and upper tail respectively (in proportion from 0 to 1)
        that lead to flagging a measurement as a buddy outlier. If None, the respective
        values from `settings.BUDDY_LOW_ALPHA` and `settings.BUDDY_HIGH_ALPHA` are used.
    station_outlier_threshold : numeric, optional
        Maximum proportion (from 0 to 1) of buddy-outlier measurements after which the
        respective station is flagged as a buddy outlier. If None, the value from
        `settings.BUDDY_STATION_OUTLIER_THRESHOLD` is used.
    keep_isolated : bool, default False
        Whether to keep isolated stations (those with fewer than `buddy_min_n` buddies,
        which cannot be evaluated). By default they are discarded along with the buddy
        outliers; set to True to exclude them from the returned list.

    Returns
    -------
    ts_df, discard_stations : pandas.DataFrame, list
        The (unchanged) time series data frame and the list of station ids to discard,
        i.e. those flagged as buddy outliers and (unless `keep_isolated`) those flagged
        as isolated (fewer than `buddy_min_n` buddies).
    """
    if station_gser is None:
        warnings.warn(
            "Skipping `flag_buddies`: no station geometry was provided.",
            stacklevel=2,
        )
        return ts_df, []
    if buddy_radius is None:
        buddy_radius = settings.BUDDY_RADIUS
    if buddy_min_n is None:
        buddy_min_n = settings.BUDDY_MIN_N
    if low_alpha is None:
        low_alpha = settings.BUDDY_LOW_ALPHA
    if high_alpha is None:
        high_alpha = settings.BUDDY_HIGH_ALPHA
    if station_outlier_threshold is None:
        station_outlier_threshold = settings.BUDDY_STATION_OUTLIER_THRESHOLD

    # only consider stations that have both time series data and a location
    stations = ts_df.columns.intersection(station_gser.index)
    ts_df = ts_df[stations]
    gser = station_gser.loc[stations]

    # pairwise distances in a metric CRS, then boolean neighbourhood (excluding self)
    gser_m = gser.to_crs(gser.estimate_utm_crs())
    dist_df = gser_m.apply(lambda geom: gser_m.distance(geom))
    neighbors_df = (dist_df > 0) & (dist_df <= buddy_radius)

    low_z = norm.ppf(low_alpha)
    high_z = norm.ppf(high_alpha)

    buddy_outlier_stations = []
    isolated_stations = []
    for station in stations:
        neighbor_ser = neighbors_df.loc[station]
        buddy_cols = neighbor_ser[neighbor_ser].index
        if len(buddy_cols) < buddy_min_n:
            isolated_stations.append(station)
            continue
        station_ser = ts_df[station]
        # nothing to evaluate if the station itself has no valid measurements (it is not
        # isolated - it has buddies - so it is simply left un-flagged)
        if not station_ser.notna().any():
            continue
        buddy_ts_df = ts_df[buddy_cols]
        # time steps with enough valid buddies to compute robust statistics
        evaluable_ser = buddy_ts_df.notna().sum(axis="columns") >= buddy_min_n
        if not evaluable_ser.any():
            isolated_stations.append(station)
            continue
        median_ser = buddy_ts_df.median(axis="columns")
        # per-time-step robust scale of the buddies (vectorized Qn over the time steps,
        # matching `_qn_row`/`scale.qn_scale` but ~orders of magnitude faster)
        qn_ser = pd.Series(_qn_rows(buddy_ts_df.to_numpy()), index=buddy_ts_df.index)
        z_ser = (station_ser - median_ser) / qn_ser
        outlier_ser = ~z_ser.between(low_z, high_z, inclusive="neither") & evaluable_ser
        if outlier_ser.sum() / evaluable_ser.sum() > station_outlier_threshold:
            buddy_outlier_stations.append(station)

    discard_stations = list(buddy_outlier_stations)
    if not keep_isolated:
        discard_stations += isolated_stations
    return ts_df, discard_stations


########################################################################################
# pipeline
#
# A QC step is any callable with the signature
#     step(ts_df, **step_kwargs) -> tuple[ts_df, discarded_station_ids]
# i.e. it takes the (wide) time series data frame plus its own keyword arguments, and
# returns a possibly transformed `ts_df` together with the list of station ids to
# discard. Station-discarding steps leave `ts_df` untouched and return the ids to drop;
# transforms (e.g. `adjust_elevation`) return the new `ts_df` and an empty list. The
# pipeline does the dropping and records it, so the per-step accounting stays in one
# place. The built-in functions above already follow this contract, so they double as
# pipeline steps - referenced by their function name (resolved against this module) -
# and arbitrary user callables can be mixed into the `steps` list. Station metadata
# derived from the constructor arguments (`station_gser`, `station_elevation_ser`) is
# auto-populated into whichever steps declare it as a parameter; a *default* step whose
# metadata is absent is omitted. The buddy check is deliberately not a default step (see
# `settings.DEFAULT_QC_STEPS`).


class QCPipeline:
    """Chain of QC steps applied to a (wide) time series data frame.

    The pipeline runs an ordered list of steps, dropping the stations that each step
    flags (and applying any value transformation, e.g. the elevation adjustment). Which
    steps run and in which order is controlled by the `steps` argument; each step's
    parameters are passed as its own dict in the positionally-matched `step_kwargs`
    list.

    Parameters
    ----------
    stations : geopandas.GeoDataFrame or geopandas.GeoSeries, optional
        Station locations indexed by the station id, either as a geo-data frame or as
        the geometry geoseries directly. Used to auto-populate the `station_gser`
        argument of the steps that declare it (`flag_mislocated`, `flag_buddies`); if
        None, those steps are omitted from the defaults (and self-skip with a warning if
        listed explicitly).
    elevation : str or pandas.Series, optional
        Source of the per-station elevation used by `adjust_elevation`, as either a
        column of `stations` (str) or a series indexed by the station id. Defaults to
        the column named in `settings.ELEVATION_COL`. Used to auto-populate the
        `station_elevation_ser` argument; if it cannot be resolved (e.g. the column is
        absent), `adjust_elevation` is omitted from the defaults. It (like the geometry)
        can always be overridden per step via `step_kwargs`.
    steps : list of str or callable, optional
        Ordered list of steps to run. Each item is either the name of a built-in
        function (one of `settings.DEFAULT_QC_STEPS` plus `"flag_buddies"`,
        `"mask_outliers"`) or a callable with the signature
        `step(ts_df, **kwargs) -> (ts_df, discarded_station_ids)`. If None,
        `settings.DEFAULT_QC_STEPS` is used, omitting steps whose station metadata is
        absent (the buddy check is *not* a default step - add it with, e.g.,
        `steps=[*settings.DEFAULT_QC_STEPS, "flag_buddies"]`).
    step_kwargs : list of dict, optional
        Per-step keyword arguments, positionally matched to `steps` (so its length must
        equal that of `steps`). Each dict is forwarded to the corresponding step, on top
        of the auto-populated station metadata (which it can override); omit it (or pass
        `{}`) to fall back to the `settings.*` defaults. Only valid when `steps` is
        given explicitly; when `steps` is None the defaults are built automatically.

    Attributes
    ----------
    discarded_ : dict
        Mapping of step name (the function name) to the list of station ids it
        discarded, populated by `apply`.
    """

    def __init__(
        self,
        *,
        stations: gpd.GeoDataFrame | gpd.GeoSeries | None = None,
        elevation: str | pd.Series | None = None,
        steps: Sequence[str | Callable] | None = None,
        step_kwargs: Sequence[dict] | None = None,
    ):
        # resolve elevation *before* reducing `stations` to its geometry, so a column
        # name can still be looked up on the (geo-)data frame
        if elevation is None:
            # get the default name from settings
            elevation = settings.ELEVATION_COL
        if isinstance(stations, pd.DataFrame) and elevation in stations.columns:
            # elevation is a column name
            elevation = stations[elevation]
        # at this point, elevation is either a series mapping station ids to elevation
        # values, or we set it to None
        if isinstance(elevation, pd.Series):
            self.elevation_ser = elevation
        else:
            self.elevation_ser = None

        # resolve the station geometry geoseries
        if isinstance(stations, gpd.GeoDataFrame):
            stations = stations.geometry
        # at this point, stations is either a geo-series or we set it to None
        if isinstance(stations, gpd.GeoSeries):
            self.station_gser = stations
        else:
            self.station_gser = None

        if steps is None:
            # canonical default sequence (with empty per-step kwargs)
            if step_kwargs is not None:
                raise ValueError(
                    "`step_kwargs` is only valid together with an explicit `steps` list"
                )
            steps = list(settings.DEFAULT_QC_STEPS)
            step_kwargs = [{} for _ in steps]
            default = True
        else:
            # an explicit `steps` may mix built-in names (str) and user callables
            if step_kwargs is None:
                step_kwargs = [{} for _ in steps]
            elif len(step_kwargs) != len(steps):
                # if provided, `step_kwargs` must positionally match `steps`
                raise ValueError(
                    f"`step_kwargs` has length {len(step_kwargs)} but `steps` has "
                    f"length {len(steps)}; they must match positionally."
                )
            default = False

        # station metadata auto-populated into the steps that declare it as a parameter
        metadata = {
            "station_gser": self.station_gser,
            "station_elevation_ser": self.elevation_ser,
        }
        # resolve each step to a callable (a string names a function of this module;
        # anything else must already be a step callable) and build its keyword args,
        # injecting the station metadata it declares unless already provided. A default
        # step whose required metadata is absent is omitted from the sequence
        self.steps = []
        self.step_kwargs = []
        for step, kwargs in zip(steps, step_kwargs):
            if isinstance(step, str):
                func = globals().get(step)
                if not callable(func):
                    raise ValueError(
                        f"Unknown step {step!r}; pass the name of a `meteora.qc` step "
                        "function or a callable."
                    )
            elif callable(step):
                func = step
            else:
                raise TypeError(
                    f"Step {step!r} must be a step name (str) or a callable."
                )
            kwargs = dict(kwargs)
            params = inspect.signature(func).parameters
            skip = False
            for name, value in metadata.items():
                if name not in params or name in kwargs:
                    continue
                if value is None:
                    # cannot supply metadata the step needs: omit it from the defaults,
                    # otherwise leave the step to self-skip (warns) at apply time
                    if default:
                        skip = True
                        break
                else:
                    kwargs[name] = value
            if skip:
                continue
            self.steps.append(func)
            self.step_kwargs.append(kwargs)

        # init discarded_ dict
        self.discarded_ = {}

    def apply(self, ts_df: pd.DataFrame, *, copy: bool = True) -> pd.DataFrame:
        """Run the QC steps on a (wide) time series data frame.

        Parameters
        ----------
        ts_df : pandas.DataFrame
            Wide time series data frame with stations as columns and time as index.
        copy : bool, default True
            Whether to operate on a copy of `ts_df` (leaving the input untouched).

        Returns
        -------
        ts_df : pandas.DataFrame
            Quality-controlled (and possibly elevation-adjusted) time series data frame,
            with the discarded stations dropped. The ids discarded by each step are
            available in the `discarded_` attribute; their union is in
            `discarded_stations`.
        """
        if copy:
            ts_df = ts_df.copy()
        self.discarded_ = {}
        for i, (step, kwargs) in enumerate(zip(self.steps, self.step_kwargs)):
            # the step name (its function name) keys the per-step `discarded_` record
            name = getattr(step, "__name__", f"step_{i}")
            ts_df, discarded = step(ts_df, **kwargs)
            # only account for/drop stations still present
            discarded = [station for station in discarded if station in ts_df.columns]
            self.discarded_[name] = discarded
            ts_df = ts_df.drop(columns=discarded)
        return ts_df

    @property
    def discarded_stations(self) -> list:
        """Union of the stations discarded across all steps (after `apply`)."""
        discarded = set()
        for stations in self.discarded_.values():
            discarded.update(stations)
        return sorted(discarded)

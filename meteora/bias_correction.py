"""Station bias correction utilities.

Provides functions to load fitted correction models from Hugging Face Hub and
to apply them to LCD temperature observations using meteora data structures.

Currently supports radiation-based bias correction. The module is structured to
accommodate multivariate correction in future extensions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import geopandas as gpd
import numpy as np
import pandas as pd

try:
    import huggingface_hub
except ImportError:
    huggingface_hub = None

try:
    from skops import io as skops_io
except ImportError:
    skops_io = None


try:
    import xarray as xr
except ImportError:
    xr = None

try:
    import xvec  # noqa: F401 - registers .xvec accessor on xarray objects
except ImportError:
    xvec = None

if TYPE_CHECKING:
    from scipy import stats
    from sklearn.base import BaseEstimator, TransformerMixin
    from sklearn.utils.validation import check_is_fitted
else:
    try:
        from scipy import stats
        from sklearn.base import BaseEstimator, TransformerMixin
        from sklearn.utils.validation import check_is_fitted
    except ImportError:
        BaseEstimator = object
        TransformerMixin = object

        def check_is_fitted(*args, **kwargs):
            """Check if the estimator is fitted.

            Placeholder that raises ImportError when called.
            """
            raise ImportError("scikit-learn is required for this feature")

        stats = None

from meteora import settings
from meteora.optional import require_optional

_HUB_DEPS = {"huggingface_hub": huggingface_hub, "skops": skops_io}
_HUB_EXTRA = "hub"
_XVEC_DEPS = {"xarray": xr, "xvec": xvec}
_XVEC_EXTRA = "xvec"


_DEFAULT_MODEL_FILENAME = "model.skops"


class BestScaleRadiationTransformer(BaseEstimator, TransformerMixin):
    """Select the best radiation rolling-sum window and apply it.

    During `fit`, evaluates each candidate window size in *window_minutes*
    by Pearson correlation with the target and stores the best one as
    `best_scale_`. During `transform`, applies a rolling sum of that
    window to the radiation column and returns a single-column DataFrame.

    Parameters
    ----------
    window_minutes : sequence of int
        Candidate window sizes (in minutes) to evaluate.
    time_col : str, default "time"
        Column of X containing datetime values.
    radiation_col : str, default `meteora.settings.ECV_RADIATION_SHORTWAVE`
        Column of X containing raw shortwave radiation values.
    """

    def __init__(
        self,
        window_minutes: Sequence[int],
        *,
        time_col: str | None = None,
        radiation_col: str | None = None,
    ):
        self.window_minutes = window_minutes
        if time_col is None:
            time_col = settings.TIME_COL
        self.time_col = time_col
        if radiation_col is None:
            radiation_col = settings.ECV_RADIATION_SHORTWAVE
        self.radiation_col = radiation_col

    def _apply_rolling(self, X, window_minutes):
        rad_ser = pd.Series(
            X[self.radiation_col].values,
            index=pd.DatetimeIndex(X[self.time_col].values),
        ).sort_index()
        rolled = rad_ser.rolling(
            pd.Timedelta(minutes=window_minutes), min_periods=1
        ).sum()
        return X[self.time_col].map(rolled)

    def fit(self, X, y):
        """Fit by selecting the window size most correlated with the target."""
        if stats is None:
            raise ImportError(
                "BestScaleRadiationTransformer.fit requires scikit-learn extras. "
                "Install with: pip install meteora[sk]"
            )
        X = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X
        y_arr = np.asarray(y, dtype=float)

        best_r = -np.inf
        best_scale = list(self.window_minutes)[0]
        for w in self.window_minutes:
            x_vals = self._apply_rolling(X, w)
            mask = x_vals.notna() & np.isfinite(y_arr)
            if mask.sum() < 2:
                continue
            r = stats.pearsonr(x_vals[mask].values, y_arr[mask]).statistic
            if r > best_r:
                best_r = r
                best_scale = w

        self.best_scale_ = best_scale
        return self

    def transform(self, X):
        """Apply the rolling sum with the best window size found during fit."""
        check_is_fitted(self)
        X = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X
        return self._apply_rolling(X, self.best_scale_).to_frame(self.radiation_col)


def parse_hf_path(model_str: str) -> tuple[str, str]:
    """Parse an HF Hub model string into `(repo_id, filename)`.

    Accepts two forms:

    * `"username/repo-name"` — filename defaults to `model.skops`
    * `"username/repo-name/filename.skops"` — explicit filename

    Parameters
    ----------
    model_str : str
        HF Hub model string in one of the two accepted forms.

    Returns
    -------
    repo_id : str
        The HF Hub repository ID, e.g. `"username/repo-name"`.
    filename : str
        The filename within the repository.
    """
    parts = model_str.split("/", maxsplit=2)
    if len(parts) == 2:
        return model_str, _DEFAULT_MODEL_FILENAME
    if len(parts) == 3:
        return f"{parts[0]}/{parts[1]}", parts[2]
    raise ValueError(
        "Expected model string in 'username/repo-name' or "
        f"'username/repo-name/filename' format, got {model_str!r}"
    )


def load_correction_model(
    repo_id: str,
    filename: str,
    trusted: Sequence[str],
    token: str | None = None,
) -> Any:
    """Download and load a bias correction model from a Hugging Face Hub repository.

    Parameters
    ----------
    repo_id : str
        Hugging Face Hub repository ID, e.g. `"username/my-models"`.
    filename : str
        Name of the `.skops` file in the repository.
    trusted : list of str
        Trusted types required to deserialize the model. Obtain this list via
        `skops.io.get_untrusted_types(file=local_path)` and review it before
        trusting.
    token : str, optional
        Hugging Face API token for private repositories.

    Returns
    -------
    object
        The deserialized scikit-learn pipeline or model.
    """
    require_optional(
        _HUB_DEPS,
        extra=_HUB_EXTRA,
        feature="Loading correction models from Hugging Face Hub",
    )

    local_path = huggingface_hub.hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        token=token,
    )
    return skops_io.load(local_path, trusted=trusted)


_SINGLE_REF_COL = "__ref__"


def _extract_ref_radiation(
    ref_ts: pd.Series | pd.DataFrame | xr.Dataset,
    radiation_var: str,
    ref_stations_gdf: gpd.GeoDataFrame | None,
) -> tuple[pd.DataFrame, gpd.GeoDataFrame | None]:
    """Normalize `ref_ts` into a wide radiation DataFrame and station geometries.

    Single source of truth for input parsing. Every supported `ref_ts` form is
    reduced to a wide DataFrame (time × ref_station_id) so the downstream compute
    loop is unaware of the original structure.

    Returns
    -------
    rad_wide_df : pd.DataFrame
        Wide radiation values, indexed by time with one column per ref station. A
        single column signals uniform correction; multiple columns signal
        per-LCD-station correction via spatial join.
    ref_stations_gdf : gpd.GeoDataFrame or None
        Geometries for the ref stations in `rad_wide_df.columns`, indexed by
        station id. `None` when only one ref station is present.
    """
    if isinstance(ref_ts, (pd.Series, pd.DataFrame)):
        ref_ser = ref_ts[radiation_var] if isinstance(ref_ts, pd.DataFrame) else ref_ts
        if isinstance(ref_ser.index, pd.MultiIndex):
            station_level = ref_ser.index.names[0]
            rad_wide_df = ref_ser.unstack(level=station_level).dropna(
                how="all", axis="columns"
            )
            if ref_stations_gdf is None:
                raise ValueError(
                    "ref_stations_gdf is required when ref_ts is a long "
                    "(MultiIndex) Series or DataFrame"
                )
            ref_stations_gdf = ref_stations_gdf.loc[
                ref_stations_gdf.index.isin(rad_wide_df.columns)
            ]
            return rad_wide_df, ref_stations_gdf
        return ref_ser.to_frame(name=_SINGLE_REF_COL), None

    require_optional(
        _XVEC_DEPS,
        extra=_XVEC_EXTRA,
        feature="apply_bias_correction with an xr.Dataset ref_ts",
    )
    rad_wide_df = (
        ref_ts[radiation_var]
        .set_index(geometry="station_id")
        .rename(geometry="station_id")
        .to_pandas()
        .T.dropna(  # to_pandas() yields station × time; transpose to time × station
            how="all", axis="columns"
        )
    )
    if rad_wide_df.shape[1] == 1:
        return rad_wide_df, None
    ref_stations_gdf = gpd.GeoDataFrame(
        {"station_id": ref_ts.coords["station_id"].values},
        geometry=list(ref_ts.coords["geometry"].values),
        crs=ref_ts.geometry.crs,
    ).set_index("station_id")
    ref_stations_gdf = ref_stations_gdf.loc[
        ref_stations_gdf.index.isin(rad_wide_df.columns)
    ]
    return rad_wide_df, ref_stations_gdf


def apply_bias_correction(
    lcd_ts_df: pd.DataFrame,
    ref_ts: pd.Series | pd.DataFrame | xr.Dataset,
    model: Any | str,
    lcd_stations_gdf: gpd.GeoDataFrame | None = None,
    ref_stations_gdf: gpd.GeoDataFrame | None = None,
    radiation_var: str | None = None,
    trusted: Sequence[str] | None = None,
    token: str | None = None,
) -> pd.DataFrame:
    """Apply radiation-based bias correction to LCD temperature observations.

    The bias (ΔT) driven by shortwave radiation is predicted by `model` and subtracted
    from the raw LCD observations. `ref_ts` may be any of the three data structures
    supported by meteora, each in wide (single ref station) or long (multi-ref station)
    form:

    * **pd.Series** — always univariate (radiation only):

      - *wide* (flat DatetimeIndex): single ref station; applied uniformly to every LCD
        station. `lcd_stations_gdf` and `ref_stations_gdf` are ignored.
      - *long* (MultiIndex station × time): per-LCD-station correction via spatial join;
        `lcd_stations_gdf` and `ref_stations_gdf` are required.

    * **pd.DataFrame** — potentially multivariate (currently univariate):

      - *wide* (flat DatetimeIndex): single ref station; `radiation_var` selects the
        relevant column and the correction is applied uniformly to every LCD station.
        `lcd_stations_gdf` and `ref_stations_gdf` are ignored.
      - *long* (MultiIndex station × time): per-LCD-station correction via spatial join;
        `radiation_var` selects the column within each station slice. `lcd_stations_gdf`
        and `ref_stations_gdf` are required.

    * **xr.Dataset** (vector data cube with `geometry` GeometryIndex):

      - *single ref station*: applied uniformly; `lcd_stations_gdf` is optional and
        `ref_stations_gdf` is ignored.
      - *multi-station*: per-LCD-station correction via spatial join using the cube
        geometry; `lcd_stations_gdf` is required, `ref_stations_gdf` is ignored.

    Parameters
    ----------
    lcd_ts_df : pd.DataFrame
        Raw LCD temperature time series, in long or wide format. The returned data frame
        preserves the input shape.
    ref_ts : pd.Series or pd.DataFrame or xr.Dataset
        Reference meteorological data, in long or wide format.
    model : sklearn Pipeline or str
        Fitted bias correction pipeline, or a Hugging Face Hub identifier. Accepts
        `"username/repo-name"` (uses `model.skops` by default) or
        `"username/repo-name/filename.skops"` for an explicit file. When a string is
        given, `trusted` must also be provided.
    lcd_stations_gdf : gpd.GeoDataFrame, optional
        LCD station data, required for multi-station reference data inputs, ignored
        otherwise.
    ref_stations_gdf : gpd.GeoDataFrame, optional
        Reference station data, indexed by station ID, required for multi-station
        reference data inputs, ignored for single-station reference data or when
        providing reference data as a vector data cube (which already integrages the
        geometry).
    radiation_var : str, optional
        Name of the radiation variable/column. If not provided, the value from
        `settings.ECV_RADIATION_SHORTWAVE` (`"radiation_shortwave"`) is used. Not used
        for key-like data selection when `ref_ts` is a single-station series, but always
        passed as the feature column name to `model.predict`.
    trusted : list of str, optional
        Trusted types for skops deserialization, required when `model` is a string. See
        `skops.io.get_untrusted_types` for how to obtain this list.
    token : str, optional
        Hugging Face API token, used when `model` is a string pointing to a private
        repository.

    Returns
    -------
    ts_df : pd.DataFrame
        Bias-corrected temperature time series in the same form as `lcd_ts_df`. For
        wide inputs, fully-NaN rows are dropped; for long inputs, the result is
        restacked so any NaN entries are dropped as a side effect.
    """
    if radiation_var is None:
        radiation_var = settings.ECV_RADIATION_SHORTWAVE

    if isinstance(model, str):
        repo_id, filename = parse_hf_path(model)
        model = load_correction_model(repo_id, filename, trusted=trusted, token=token)

    lcd_was_long = isinstance(lcd_ts_df.index, pd.MultiIndex)
    if lcd_was_long:
        lcd_var = lcd_ts_df.columns[0]
        station_level = lcd_ts_df.index.names[0]
        lcd_wide = lcd_ts_df[lcd_var].unstack(level=station_level)
    else:
        lcd_wide = lcd_ts_df

    rad_wide_df, ref_stations_gdf = _extract_ref_radiation(
        ref_ts, radiation_var, ref_stations_gdf
    )

    if rad_wide_df.shape[1] == 1:
        # Uniform correction — every LCD column maps to the single ref station
        nearest_ref_ser = pd.Series(rad_wide_df.columns[0], index=lcd_wide.columns)
    else:
        if lcd_stations_gdf is None:
            raise ValueError(
                "lcd_stations_gdf is required when ref_ts has multiple "
                "reference stations"
            )
        # Replicate geopandas' right-index column naming: unnamed → "index_right";
        # named but conflicting with left index or left columns → "{name}_right";
        # otherwise → "{name}".
        right_name = ref_stations_gdf.index.name
        if right_name is None:
            right_col = "index_right"
        elif (
            right_name == lcd_stations_gdf.index.name
            or right_name in lcd_stations_gdf.columns
        ):
            right_col = f"{right_name}_right"
        else:
            right_col = right_name
        nearest_ref_ser = lcd_stations_gdf.sjoin_nearest(ref_stations_gdf)[right_col]
        # sjoin_nearest can return multiple rows per left geometry when distances
        # tie; keep only the first match to guarantee scalar lookup
        nearest_ref_ser = nearest_ref_ser[
            ~nearest_ref_ser.index.duplicated(keep="first")
        ]

    lcd_cols = [col for col in lcd_wide.columns if col in nearest_ref_ser.index]

    yhat_dict = {}
    for col in lcd_cols:
        rad_ser = rad_wide_df[nearest_ref_ser[col]]
        yhat_dict[col] = pd.Series(
            model.predict(
                pd.DataFrame({"time": rad_ser.index, radiation_var: rad_ser.values})
            ),
            index=rad_ser.index,
        )

    # Match the index name so pandas sub() aligns by value without triggering
    # _join_multi (which fails when names differ, e.g. None vs "time").
    yhat_df = pd.DataFrame(yhat_dict).rename_axis(lcd_wide.index.name)
    cor_wide = lcd_wide.sub(yhat_df).dropna(how="all")

    if lcd_was_long:
        return (
            cor_wide.stack()
            .swaplevel()
            .sort_index()
            .to_frame(name=lcd_var)
            .rename_axis(index=lcd_ts_df.index.names)
        )
    return cor_wide

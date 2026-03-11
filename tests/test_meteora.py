"""Tests for Meteora."""

import importlib
import inspect
import json
import logging as lg
import os
import sys
import unittest
from collections.abc import Generator
from os import path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pook
import pytest
import xarray as xr
import xclim.indices as xci
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

from meteora import climate_indices, qc, settings, units, utils
from meteora.clients import (
    AemetClient,
    AgrometeoClient,
    ASOSOneMinIEMClient,
    AWELClient,
    GHCNHourlyClient,
    METARASOSIEMClient,
    MeteocatClient,
    MeteoSwissClient,
    NetatmoClient,
)
from meteora.clients.base import BaseClient
from meteora.clients.mixins import (
    StationPartitionedTSMixin,
    StationsEndpointMixin,
    TimePartitionedTSMixin,
    VariablePartitionedTSMixin,
    VariablesEndpointMixin,
    VariablesHardcodedMixin,
)

tests_dir = "tests"
tests_data_dir = path.join(tests_dir, "data")


@pytest.fixture
def unload_xarray(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Fake that xarray is not installed.

    Source: https://stackoverflow.com/a/79280624
    """
    modules = {
        module: sys.modules[module]
        for module in list(sys.modules)
        if module.startswith("xarray") or module == "xarray"
    }
    for module in modules:
        # ensure that `xarray` and all its submodules are not loadable
        monkeypatch.setitem(sys.modules, module, None)

    with pytest.raises(ImportError):
        # ensure that `xarray` cannot be imported
        import xarray  # noqa: F401

    importlib.reload(utils)
    yield  # undo the monkeypatch
    for module, original in modules.items():
        if original is None:
            sys.modules.pop(module, None)
        else:
            sys.modules[module] = original
    importlib.reload(utils)  # make `xarray` available again


@pytest.fixture
def unload_xclim(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Fake that xclim is not installed."""
    modules = {
        module: sys.modules[module]
        for module in list(sys.modules)
        if module.startswith("xclim") or module == "xclim"
    }
    for module in modules:
        monkeypatch.setitem(sys.modules, module, None)

    with pytest.raises(ImportError):
        import xclim  # noqa: F401

    importlib.reload(climate_indices)
    yield
    for module, original in modules.items():
        if original is None:
            sys.modules.pop(module, None)
        else:
            sys.modules[module] = original
    importlib.reload(climate_indices)


def override_settings(module, **kwargs):
    class OverrideSettings:
        def __enter__(self):
            self.old_values = {}
            for key, value in kwargs.items():
                self.old_values[key] = getattr(module, key)
                setattr(module, key, value)

        def __exit__(self, type, value, traceback):
            for key, value in self.old_values.items():
                setattr(module, key, value)

    return OverrideSettings()


class DummyUnitsClient(VariablesHardcodedMixin, BaseClient):
    X_COL = "x"
    Y_COL = "y"
    CRS = "epsg:4326"
    _stations_gdf_id_col = settings.STATIONS_ID_COL
    _ts_df_time_col = settings.TIME_COL
    _ts_df_stations_id_col = settings.STATIONS_ID_COL
    _variables_id_col = "code"
    _variables_label_col = "label"
    _variables_dict = {
        "tmpf": "Air Temperature",
        "dwpf": "Dew Point Temperature",
    }
    _variable_units_dict = {"tmpf": "degF", "dwpf": "degF"}
    _ecv_dict = {
        settings.ECV_TEMPERATURE: "tmpf",
        settings.ECV_DEW_POINT_TEMPERATURE: "dwpf",
    }
    _ts_endpoint = "dummy"

    def __init__(self):
        self.region = [0.0, 0.0, 1.0, 1.0]
        super().__init__()

    def get_ts_df(self, variables, *args, **kwargs):
        return self._get_ts_df(variables, *args, **kwargs)

    def _ts_df_from_endpoint(self, ts_params):
        variable_ids = ts_params["variable_ids"]
        if isinstance(variable_ids, pd.Series):
            variable_ids = list(variable_ids)
        idx = pd.MultiIndex.from_product(
            [["A"], pd.date_range("2020-01-01", periods=2, freq="D")],
            names=[settings.STATIONS_ID_COL, settings.TIME_COL],
        )
        data = {}
        for variable_id in variable_ids:
            if variable_id == "tmpf":
                data[variable_id] = [32.0, 50.0]
            else:
                data[variable_id] = [30.0, 40.0]
        return pd.DataFrame(data, index=idx)


class TestUtils(unittest.TestCase):
    def setUp(self):
        self.ts_df = pd.read_csv(
            path.join(tests_data_dir, "ts-df.csv"),
            index_col=["station_id", "time"],
            parse_dates=True,
            date_format="%Y-%m-%d %H:%M:%S",
        )
        self.wide_ts_df = pd.read_csv(
            path.join(tests_data_dir, "wide-ts-df.csv"),
            index_col="time",
            parse_dates=True,
        )
        self.stations_gdf = gpd.read_file(
            path.join(tests_data_dir, "stations.gpkg")
        ).set_index(settings.STATIONS_ID_COL)

    def test_geo_utils(self):
        # geo utils
        # dms to dd
        dms_ser = pd.Series(["413120N"])
        dd_ser = utils.dms_to_decimal(dms_ser)
        self.assertTrue(is_numeric_dtype(dd_ser))

    def test_long_to_wide(self):
        wide_ts_df = utils.long_to_wide(self.ts_df)
        # test wide data frame form
        self.assertIsInstance(wide_ts_df.columns, pd.MultiIndex)
        self.assertIsInstance(wide_ts_df.index, pd.DatetimeIndex)
        # with only one variable, we should have only one column level
        wide_ts_df = utils.long_to_wide(self.ts_df, variables=["temperature"])
        self.assertEqual(len(wide_ts_df.columns.names), 1)
        self.assertIsInstance(wide_ts_df.index, pd.DatetimeIndex)

    def test_attach_units(self):
        ts_df = pd.DataFrame({"temperature": [1.0, 2.0]})
        units_map = {"temperature": "degC"}
        result = units.attach_units(ts_df, units_map)
        self.assertEqual(result.attrs["units"]["temperature"], "degC")

    def test_convert_units(self):
        ts_df = pd.DataFrame({"temperature": [32.0, 68.0]})
        source_units = {"temperature": "degF"}
        target_units = {"temperature": "degC"}
        result = units.convert_units(ts_df, target_units, source_units=source_units)
        self.assertAlmostEqual(result["temperature"].iloc[0], 0.0, places=6)
        self.assertAlmostEqual(result["temperature"].iloc[1], 20.0, places=6)
        self.assertEqual(result.attrs["units"]["temperature"], "degC")
        ts_df_units = units.attach_units(ts_df, source_units)
        result_from_attrs = units.convert_units(
            ts_df_units,
            target_units,
            source_units={"temperature": "degC"},
        )
        pd.testing.assert_frame_equal(result, result_from_attrs)

    @pytest.mark.usefixtures("unload_xarray")
    def test_long_to_cube_missing_xarray(self):
        # test that we can only call this function if xarray/xvec are installed
        with pytest.raises(ImportError):
            utils.long_to_cube(self.ts_df, self.stations_gdf)

    @pytest.mark.usefixtures("unload_xarray")
    def test_long_to_stationbench_missing_xarray(self):
        # test that we can only call this function if xarray/xvec are installed
        with pytest.raises(ImportError):
            utils.long_to_stationbench(self.ts_df, self.stations_gdf)

    def test_long_to_cube(self):
        pytest.importorskip("xvec")

        with pytest.raises(KeyError):
            # if stations_gdf does not cover all stations in ts_df a KeyError is also
            # raised
            utils.long_to_cube(self.ts_df, self.stations_gdf.iloc[:2])
            # attempting to convert from the wide form also raises a KeyError
            utils.long_to_cube(self.wide_ts_df, self.stations_gdf)
        # test proper conversion
        ts_cube = utils.long_to_cube(self.ts_df, self.stations_gdf)
        # test an xarray dataset is returned
        self.assertIsInstance(ts_cube, xr.Dataset)
        # test that the time column is in the coordinates
        self.assertIn(self.ts_df.index.names[1], ts_cube.coords)
        # test that the variable columns are in the data_vars
        self.assertTrue(all([var in ts_cube.data_vars for var in self.ts_df.columns]))
        # test that it has a dimension with geometry
        self.assertIn("geometry", ts_cube.xvec.geom_coords)
        self.assertIn("geometry", ts_cube.xvec.geom_coords_indexed)
        # test that there is a coordinate with the station ids and that all its values
        # are in the stations_gdf index
        self.assertIn(settings.STATIONS_ID_COL, ts_cube.coords)
        self.assertLessEqual(
            set(ts_cube[settings.STATIONS_ID_COL].values), set(self.stations_gdf.index)
        )

    def test_long_to_stationbench(self):
        pytest.importorskip("xvec")

        with pytest.raises(ValueError):
            # calling it with a wide data frame should raise a ValueError (not enough
            # values to unpack)
            utils.long_to_stationbench(self.wide_ts_df, self.stations_gdf)

        # test default dataset shape
        ts_ds = utils.long_to_stationbench(self.ts_df, self.stations_gdf)
        self.assertIsInstance(ts_ds, xr.Dataset)
        self.assertEqual(
            set(ts_ds.dims),
            {"time", "station_id"},
        )
        self.assertIn("latitude", ts_ds.coords)
        self.assertIn("longitude", ts_ds.coords)
        self.assertEqual(ts_ds["latitude"].dims, ("station_id",))
        self.assertEqual(ts_ds["longitude"].dims, ("station_id",))
        self.assertIn("2m_temperature", ts_ds.data_vars)
        self.assertIn("water_vapour", ts_ds.data_vars)
        self.assertEqual(
            ts_ds["2m_temperature"].dims,
            (settings.TIME_COL, settings.STATIONS_ID_COL),
        )
        # test time and station dim name kwargs
        dst_time_dim = "_time"
        dst_station_dim = "_station"
        self.assertEqual(
            set(
                utils.long_to_stationbench(
                    self.ts_df,
                    self.stations_gdf,
                    dst_time_dim=dst_time_dim,
                    dst_station_dim=dst_station_dim,
                ).dims
            ),
            {dst_time_dim, dst_station_dim},
        )
        # test different variable rename map (note that self.ts_df does  not have wind
        # speed)
        variable_rename_map = {"temperature": "2t"}  # , "wind_speed": "10u"
        ts_ds_renamed = utils.long_to_stationbench(
            self.ts_df, self.stations_gdf, variable_rename=variable_rename_map
        )
        for variable_name in variable_rename_map.values():
            self.assertIn(variable_name, ts_ds_renamed.data_vars)

    def test_meteo_utils(self):
        # meteo utils (heatwave detection)
        # increasing the temperature threshold should result in a less or equal number
        # of heatwave periods
        self.assertLessEqual(
            len(
                utils.get_heatwave_periods(
                    self.wide_ts_df,
                    heatwave_t_threshold=27,
                )
            ),
            len(
                utils.get_heatwave_periods(
                    self.wide_ts_df,
                    heatwave_t_threshold=25,
                )
            ),
        )
        # increasing the duration threshold should result in a less or equal number of
        # heatwave periods
        self.assertLessEqual(
            len(
                utils.get_heatwave_periods(
                    self.wide_ts_df,
                    heatwave_t_threshold=25,
                    heatwave_n_consecutive_days=3,
                )
            ),
            len(
                utils.get_heatwave_periods(
                    self.wide_ts_df,
                    heatwave_t_threshold=25,
                    heatwave_n_consecutive_days=2,
                )
            ),
        )
        # using the daily maximum temperature instead of the mean should result in a
        # greater or equal number of heatwave periods
        self.assertGreaterEqual(
            len(
                utils.get_heatwave_periods(
                    self.wide_ts_df,
                    heatwave_t_threshold=25,
                    heatwave_n_consecutive_days=2,
                    station_agg_func="max",
                )
            ),
            len(
                utils.get_heatwave_periods(
                    self.wide_ts_df,
                    heatwave_t_threshold=25,
                    heatwave_n_consecutive_days=2,
                    station_agg_func="mean",
                )
            ),
        )
        # using the max instead of the mean to aggregate the stations should result in a
        # greater or equal number of heatwave periods
        self.assertGreaterEqual(
            len(
                utils.get_heatwave_periods(
                    self.wide_ts_df,
                    heatwave_t_threshold=25,
                    heatwave_n_consecutive_days=2,
                    inter_station_agg_func="max",
                )
            ),
            len(
                utils.get_heatwave_periods(
                    self.wide_ts_df,
                    heatwave_t_threshold=25,
                    heatwave_n_consecutive_days=2,
                    inter_station_agg_func="mean",
                )
            ),
        )
        # get the time series data for the heatwave periods
        for kwargs in [{}, {"heatwave_t_threshold": 25}]:
            heatwave_ts_df = utils.get_heatwave_ts_df(
                self.wide_ts_df,
                **kwargs,
            )
            # test that the data frame has a multi-index with the heatwave periods and
            # time as well as the station ids as columns
            self.assertIsInstance(heatwave_ts_df.index, pd.MultiIndex)
            self.assertEqual(
                heatwave_ts_df.index.names,
                [
                    "heatwave",
                    self.wide_ts_df.index.name,
                ],
            )
        # test that we can also get it from the heatwave periods
        heatwave_periods = utils.get_heatwave_periods(
            self.wide_ts_df,
        )
        heatwave_ts_df = utils.get_heatwave_ts_df(
            self.wide_ts_df,
            heatwave_periods=heatwave_periods,
        )
        # test that we have an outermost index with the heatwave periods
        self.assertEqual(
            len(heatwave_ts_df.index.get_level_values("heatwave").unique()),
            len(heatwave_periods),
        )
        # test that an empty time series data frame is returned if no heatwave periods
        # are found
        # # test that a message is logged if no heatwave periods are found
        # with self.assertLogs(settings.LOG_NAME, level=lg.WARNING) as cm:
        #     settings.LOG_CONSOLE = True
        #     self.assertIn("empty", cm.output)
        ts_df = utils.get_heatwave_ts_df(self.wide_ts_df, heatwave_t_threshold=100)
        self.assertTrue(ts_df.empty)

        # logger
        def test_logging():
            utils.log("test a fake default message")
            utils.log("test a fake debug", level=lg.DEBUG)
            utils.log("test a fake info", level=lg.INFO)
            utils.log("test a fake warning", level=lg.WARNING)
            utils.log("test a fake error", level=lg.ERROR)

        test_logging()
        with override_settings(settings, LOG_CONSOLE=True):
            test_logging()
        with override_settings(settings, LOG_FILE=True):
            test_logging()

        # timestamps
        utils.ts(style="date")
        utils.ts(style="datetime")
        utils.ts(style="time")

    def test_climate_indices(self):
        # defaults from xclim should match explicit parameters
        tn_default = climate_indices.tn_days_above(self.ts_df)
        tn_sig = inspect.signature(xci.tn_days_above)
        tn_explicit = climate_indices.tn_days_above(
            self.ts_df,
            temperature_col="temperature",
            thresh=tn_sig.parameters["thresh"].default,
            freq=tn_sig.parameters["freq"].default,
            op=tn_sig.parameters["op"].default,
        )
        pd.testing.assert_frame_equal(tn_default, tn_explicit)
        self.assertIsInstance(tn_default.index, pd.DatetimeIndex)
        self.assertTrue(
            set(tn_default.columns)
            <= set(self.ts_df.index.get_level_values("station_id").unique())
        )

        hs_sig = inspect.signature(xci.hot_spell_frequency)
        hs_default = climate_indices.hot_spell_frequency(self.ts_df)
        hs_explicit = climate_indices.hot_spell_frequency(
            self.ts_df,
            temperature_col="temperature",
            thresh=hs_sig.parameters["thresh"].default,
            window=hs_sig.parameters["window"].default,
            freq=hs_sig.parameters["freq"].default,
            op=hs_sig.parameters["op"].default,
            resample_before_rl=hs_sig.parameters["resample_before_rl"].default,
        )
        pd.testing.assert_frame_equal(hs_default, hs_explicit)

        hd_sig = inspect.signature(xci.heating_degree_days)
        hd_default = climate_indices.heating_degree_days(self.ts_df)
        hd_explicit = climate_indices.heating_degree_days(
            self.ts_df,
            temperature_col="temperature",
            thresh=hd_sig.parameters["thresh"].default,
            freq=hd_sig.parameters["freq"].default,
        )
        pd.testing.assert_frame_equal(hd_default, hd_explicit)

        extra_df = self.ts_df.assign(
            **{
                settings.ECV_PRECIPITATION: 1.0,
                settings.ECV_WIND_SPEED: 2.0,
            }
        )
        wet_sig = inspect.signature(xci.wetdays)
        wet_default = climate_indices.wetdays(extra_df)
        wet_explicit = climate_indices.wetdays(
            extra_df,
            precipitation_col=settings.ECV_PRECIPITATION,
            thresh=wet_sig.parameters["thresh"].default,
            freq=wet_sig.parameters["freq"].default,
            op=wet_sig.parameters["op"].default,
        )
        pd.testing.assert_frame_equal(wet_default, wet_explicit)

        wind_sig = inspect.signature(xci.sfcWind_mean)
        wind_default = climate_indices.sfc_wind_mean(extra_df)
        wind_explicit = climate_indices.sfc_wind_mean(
            extra_df,
            wind_speed_col=settings.ECV_WIND_SPEED,
            freq=wind_sig.parameters["freq"].default,
        )
        pd.testing.assert_frame_equal(wind_default, wind_explicit)

        # multi-variable defaults use ECV names
        multi_df = self.ts_df.rename(
            columns={"water_vapour": settings.ECV_RELATIVE_HUMIDITY}
        ).assign(
            **{
                settings.ECV_DEW_POINT_TEMPERATURE: self.ts_df["temperature"],
            }
        )
        heat_index_df = climate_indices.heat_index(multi_df)
        humidex_df = climate_indices.humidex(multi_df)
        self.assertIsInstance(heat_index_df.index, pd.DatetimeIndex)
        self.assertIsInstance(humidex_df.index, pd.DatetimeIndex)

    def test_climate_indices_units_metadata(self):
        idx = pd.MultiIndex.from_product(
            [["A"], pd.date_range("2020-01-01", periods=3, freq="D")],
            names=[settings.STATIONS_ID_COL, settings.TIME_COL],
        )
        base_df = pd.DataFrame(
            {
                settings.ECV_TEMPERATURE: [20.0, 25.0, 30.0],
                settings.ECV_RELATIVE_HUMIDITY: [50.0, 60.0, 70.0],
            },
            index=idx,
        )
        df_c = units.attach_units(
            base_df,
            {
                settings.ECV_TEMPERATURE: "degC",
                settings.ECV_RELATIVE_HUMIDITY: "percent",
            },
        )
        df_f = base_df.copy()
        df_f[settings.ECV_TEMPERATURE] = (
            df_f[settings.ECV_TEMPERATURE] * 9.0 / 5.0 + 32.0
        )
        df_f = units.attach_units(
            df_f,
            {
                settings.ECV_TEMPERATURE: "degF",
                settings.ECV_RELATIVE_HUMIDITY: "percent",
            },
        )
        humidex_c = climate_indices.humidex(df_c)
        humidex_f = climate_indices.humidex(df_f)
        # xclim returns humidex in the same units as the input temperature.
        humidex_f_as_c = units.convert_units(
            humidex_f,
            {col: "degC" for col in humidex_f.columns},
            source_units={col: "degF" for col in humidex_f.columns},
        )
        pd.testing.assert_frame_equal(humidex_c, humidex_f_as_c, rtol=1e-6, atol=1e-6)
        humidex_wrong_units = climate_indices.humidex(df_c, temperature_unit="degF")
        pd.testing.assert_frame_equal(
            humidex_c, humidex_wrong_units, rtol=1e-6, atol=1e-6
        )

    @pytest.mark.usefixtures("unload_xclim")
    def test_climate_indices_missing_xclim(self):
        with pytest.raises(ImportError):
            climate_indices.tn_days_above(self.ts_df)


def test_qc():
    # read a wide ts df
    # ACHTUNG: select only 3 days so that tests run faster (comparison lineplots can be
    # slow)
    ts_df = pd.read_csv(
        path.join(tests_data_dir, "wide-ts-df.csv"), index_col="time", parse_dates=True
    ).iloc[:72]

    # test comparison lineplot
    discard_stations = ts_df.columns[:2]
    # check that there are four lines in the plot (2 mean + 2 CI lines)
    assert len(qc.comparison_lineplot(ts_df, discard_stations).lines) == 4
    # test that if we plot discarded stations individually, we get a line for each
    # discarded station (plus two for the kept ones, i.e., the mean and CI lines)
    assert (
        len(qc.comparison_lineplot(ts_df, discard_stations).lines)
        == len(discard_stations) + 2
    )
    # test that we can plot in a given axis
    fig, ax = plt.subplots()
    assert len(ax.lines) == 0
    qc.comparison_lineplot(ts_df, discard_stations, ax=ax)
    assert len(ax.lines) == 4

    # test mislocated stations
    # generate a random gdf with the same stations as ts_df
    stations_gser = gpd.GeoSeries(
        gpd.points_from_xy(
            np.random.rand(len(ts_df.columns)), np.random.rand(len(ts_df.columns))
        ),
        index=ts_df.columns,
        crs=4326,
    )
    # duplicate some station location
    src_station = ts_df.columns[0]
    dst_station = ts_df.columns[1]
    stations_gser.loc[src_station] = stations_gser.loc[dst_station]
    # test that we get the duplicated stations
    mislocated_stations = qc.get_mislocated_stations(stations_gser)
    for station in [src_station, dst_station]:
        assert station in mislocated_stations

    # test unreliable stations
    unreliable_stations = qc.get_unreliable_stations(ts_df)
    assert len(unreliable_stations) >= 0
    # test threshold (default is 0.2)
    # test that a higher threshold returns at most the same stations
    assert len(qc.get_unreliable_stations(ts_df, unreliable_threshold=0.3)) <= len(
        unreliable_stations
    )
    # test that a lower threshold returns at least the same stations
    assert len(qc.get_unreliable_stations(ts_df, unreliable_threshold=0.1)) >= len(
        unreliable_stations
    )
    # test that we get an empty list if we set the threshold to 1
    assert qc.get_unreliable_stations(ts_df, unreliable_threshold=1 == [])

    # test elevation adjustment
    # generate a random elevation series with stations as index
    station_elevation_ser = pd.Series(
        np.random.rand(len(ts_df.columns)) * 100 + 1, index=ts_df.columns
    )
    # adjust with the default lapse rate (0.0065)
    adj_ts_df = qc.elevation_adjustment(ts_df, station_elevation_ser)
    # test that the adjusted ts_df has the same shape and indexing
    assert adj_ts_df.shape == ts_df.shape
    assert adj_ts_df.index.equals(ts_df.index)
    assert adj_ts_df.columns.equals(ts_df.columns)
    # test that a higher lapse rate increases (strict) the range of the adjusted values
    # technically this may not work with elevations smaller than 1
    high_adj_ts_df = qc.elevation_adjustment(
        ts_df, station_elevation_ser, atmospheric_lapse_rate=0.2
    )
    assert adj_ts_df.min().min() > high_adj_ts_df.min().min()
    assert adj_ts_df.max().max() < high_adj_ts_df.max().max()

    # test outlier detection
    outlier_stations = qc.get_outlier_stations(ts_df)
    assert len(outlier_stations) >= 0
    # test tail range (default high_alpha=0.95, low_alpha=0.01)
    # test that a smaller tail range returns at least the same stations
    assert len(qc.get_outlier_stations(ts_df, low_alpha=0.1, high_alpha=0.9)) >= len(
        outlier_stations
    )
    # test that a bigger tail range returns at most the same stations
    assert len(qc.get_outlier_stations(ts_df, low_alpha=0.01, high_alpha=0.99)) <= len(
        outlier_stations
    )
    # test station outlier threshold (default 0.2)
    # test that a higher outlier threshold returns at most the same stations
    station_outlier_threshold = 0.3
    assert len(
        qc.get_outlier_stations(
            ts_df, station_outlier_threshold=station_outlier_threshold
        )
    ) <= len(outlier_stations)
    # test that a lower outlier threshold returns at least the same stations
    assert len(
        qc.get_outlier_stations(
            ts_df, station_outlier_threshold=station_outlier_threshold
        )
    ) >= len(outlier_stations)

    # test indoor station detection
    indoor_stations = qc.get_indoor_stations(ts_df)
    assert len(indoor_stations) >= 0
    # test correlation threshold (default 0.9)
    # test that a higher threshold returns at least the same stations
    assert len(
        qc.get_indoor_stations(ts_df, station_indoor_corr_threshold=0.95)
    ) >= len(indoor_stations)
    # test that a lower threshold returns at most the same stations
    assert len(
        qc.get_indoor_stations(ts_df, station_indoor_corr_threshold=0.85)
    ) <= len(indoor_stations)


class TestClientUnits(unittest.TestCase):
    def test_get_ts_df_units(self):
        client = DummyUnitsClient()
        ts_df = client.get_ts_df(
            [settings.ECV_TEMPERATURE, settings.ECV_DEW_POINT_TEMPERATURE]
        )
        self.assertEqual(
            ts_df.attrs["units"][settings.ECV_TEMPERATURE],
            "degF",
        )
        self.assertEqual(
            ts_df.attrs["units"][settings.ECV_DEW_POINT_TEMPERATURE],
            "degF",
        )


class TestProgress(unittest.TestCase):
    """Test the progress bar integration across real client classes."""

    REGION = "Pully, Switzerland"

    def test_default_setting(self):
        self.assertTrue(settings.SHOW_PROGRESS)

    def test_client_progress_default(self):
        client = MeteoSwissClient(region=self.REGION)
        self.assertTrue(client.progress)

    def test_client_progress_setting_override(self):
        with override_settings(settings, SHOW_PROGRESS=False):
            client = MeteoSwissClient(region=self.REGION)
            self.assertFalse(client.progress)

    def test_client_progress_init_override(self):
        for client in [
            MeteoSwissClient(region=self.REGION, progress=False),
            GHCNHourlyClient(region=self.REGION, progress=False),
            AWELClient(region="Zürich, Switzerland", progress=False),
            MeteocatClient(region="Catalunya", api_key="dummy", progress=False),
        ]:
            self.assertFalse(client.progress)

    def test_client_progress_runtime_toggle(self):
        client = MeteoSwissClient(region=self.REGION)
        self.assertTrue(client.progress)
        client.progress = False
        self.assertFalse(client.progress)
        client.progress = True
        self.assertTrue(client.progress)

    def test_should_show_progress_meteoswiss(self):
        """MeteoSwiss uses Station + Time; station is outermost."""
        client = MeteoSwissClient(region=self.REGION, progress=True)
        self.assertTrue(client._should_show_progress(StationPartitionedTSMixin))
        self.assertFalse(client._should_show_progress(TimePartitionedTSMixin))

    def test_should_show_progress_meteocat(self):
        """Meteocat uses Variable + Time; variable is outermost."""
        client = MeteocatClient(region="Catalunya", api_key="dummy", progress=True)
        self.assertTrue(client._should_show_progress(VariablePartitionedTSMixin))
        self.assertFalse(client._should_show_progress(TimePartitionedTSMixin))

    def test_should_show_progress_awel(self):
        """AWEL uses Time only; time is outermost."""
        client = AWELClient(region="Zürich, Switzerland", progress=True)
        self.assertTrue(client._should_show_progress(TimePartitionedTSMixin))
        self.assertFalse(client._should_show_progress(StationPartitionedTSMixin))

    def test_should_show_progress_ghcnh(self):
        """GHCNh overrides _ts_df_from_endpoint; no mixin shows progress."""
        client = GHCNHourlyClient(region=self.REGION, progress=True)
        self.assertFalse(client._should_show_progress(StationPartitionedTSMixin))
        self.assertFalse(client._should_show_progress(TimePartitionedTSMixin))

    def test_should_show_progress_disabled(self):
        client = MeteoSwissClient(region=self.REGION, progress=False)
        self.assertFalse(client._should_show_progress(StationPartitionedTSMixin))
        self.assertFalse(client._should_show_progress(TimePartitionedTSMixin))


class BaseClientTest:
    client_cls = None
    region = None
    variables = ["temperature", "pressure"]
    variable_codes = None
    ts_df_args = None
    ts_df_kwargs = None

    def setUp(self):
        self.client = self.client_cls(region=self.region)

    def test_region_crs(self):
        self.assertEqual(self.client.CRS, self.client.region.crs)

    def test_attributes(self):
        for attr in ["X_COL", "Y_COL", "CRS"]:
            self.assertTrue(hasattr(self.client, attr))
            self.assertIsNotNone(getattr(self.client, attr))

    def test_stations(self):
        if isinstance(self.client, StationsEndpointMixin):
            stations_gdf = self.client.stations_gdf
            assert len(stations_gdf) >= 1
            self.assertEqual(stations_gdf.index.name, settings.STATIONS_ID_COL)

    def test_variables(self):
        if isinstance(self.client, VariablesEndpointMixin):
            variables_df = self.client.variables_df
            assert len(variables_df) >= 1

    def test_time_series(self):
        if self.ts_df_args is None:
            ts_df_args = []
        else:
            ts_df_args = self.ts_df_args.copy()
        if self.ts_df_kwargs is None:
            ts_df_kwargs = {}
        else:
            ts_df_kwargs = self.ts_df_kwargs.copy()
        for variables in [self.variables, self.variable_codes]:
            ts_df = self.client.get_ts_df(self.variables, *ts_df_args, **ts_df_kwargs)
            # test data frame shape
            assert len(ts_df.columns) == len(self.variables)
            # TODO: use "station" as `level` arg?
            # ACHTUNG: using the <= because in many cases some stations are listed in
            # the stations endpoint but do not return data (maybe inactive?)
            assert len(ts_df.index.get_level_values(0).unique()) <= len(
                self.client.stations_gdf
            )
            # TODO: use "time" as `level` arg?
            assert is_datetime64_any_dtype(ts_df.index.get_level_values(1))
            # test that index is sorted - note that we need to test it as a multi-index
            # for each station because (i) we do not care if stations ids are sorted and
            # (ii) otherwise the time index alone is not unique in long data frames
            for _, _ts_df in ts_df.groupby(level="station_id"):
                assert _ts_df.droplevel("station_id").index.is_monotonic_increasing
            # test index labels
            assert ts_df.index.names == [settings.STATIONS_ID_COL, settings.TIME_COL]


class APIKeyClientTest(BaseClientTest):
    stations_response_file = None

    def setUp(self):
        self.client = self.client_cls(self.region, self.api_key)

    def test_attributes(self):
        super().test_attributes()
        self.assertTrue(hasattr(self.client, "_api_key"))
        self.assertIsNotNone(self.client._api_key)


class APIKeyHeaderClientTest(APIKeyClientTest):
    def test_attributes(self):
        super().test_attributes()
        self.assertTrue("X-API-KEY" in self.client.request_headers)
        self.assertIsNotNone(self.client.request_headers["X-API-KEY"])


class APIKeyParamClientTest(APIKeyClientTest):
    def test_attributes(self):
        super().test_attributes()
        self.assertTrue(hasattr(self.client, "_api_key_param_name"))
        api_key_param_name = self.client._api_key_param_name
        self.assertTrue(api_key_param_name in self.client.request_params)
        self.assertIsNotNone(self.client.request_params[api_key_param_name])


class OAuth2ClientTest(BaseClientTest):
    def setUp(self):
        self.client = self.client_cls(
            self.region, self.client_id, self.client_secret, token=self.token
        )


class AemetClientTest(APIKeyParamClientTest, unittest.TestCase):
    client_cls = AemetClient
    region = "Catalunya"
    api_key = os.getenv("AEMET_API_KEY", "")
    # ACHTUNG: the test data that we have for AEMET does NOT include the "pressure"
    # variable even though this is a listed variable in the AEMET API, which probably
    # means that the test data stations do NOT have that variable - TODO: raise an
    # informative error if the variable is not available for the specified stations
    variables = ["temperature", "precipitation"]
    variable_codes = ["ta", "prec"]

    @pook.on
    def test_all(self):
        # test stations, variables and time series in the same method because we need
        # to mock the same requests
        with open(path.join(tests_data_dir, "aemet-stations.json")) as src:
            response_dict = json.load(src)
            pook.get(
                f"{AemetClient._stations_endpoint}?api_key={self.api_key}",
                response_json=response_dict,
                persist=True,
            )
        with open(path.join(tests_data_dir, "aemet-stations-datos.json")) as src:
            pook.get(response_dict["datos"], response_json=json.load(src), persist=True)
        super().test_stations()

        with open(path.join(tests_data_dir, "aemet-var-ts.json")) as src:
            response_dict = json.load(src)
            pook.get(
                f"{AemetClient._variables_endpoint}?api_key={self.api_key}",
                response_json=response_dict,
                persist=True,
            )
        with open(path.join(tests_data_dir, "aemet-var-ts-metadatos.json")) as src:
            pook.get(
                response_dict["metadatos"],
                response_json=json.load(src),
            )

        with open(path.join(tests_data_dir, "aemet-var-ts-datos.json")) as src:
            pook.get(
                response_dict["datos"],
                response_json=json.load(src),
            )

        # test stations
        super().test_stations()

        # test variables
        # variables_df = self.client.variables_df
        assert len(self.client.variables_df) >= 1

        # test time series
        self.client.get_ts_df(self.variables)
        # ACHTUNG: for some reason (internal to Aemet's API), we get more stations
        # from the stations endpoint than from the time series endpoint, so the
        # assertions of the `test_time_series` method would fail
        # super().test_time_series()

    # the tests are already done in `test_all` so we override it here with empty methods
    def test_stations(self):
        pass

    def test_variables(self):
        pass

    def test_time_series(self):
        pass


class AgrometeoClientTest(BaseClientTest, unittest.TestCase):
    client_cls = AgrometeoClient
    region = "Pully, Switzerland"
    variable_codes = [1, 18]
    start_date = "2022-03-22"
    end_date = "2022-03-23"
    ts_df_args = [start_date, end_date]


class AWELClientTest(BaseClientTest, unittest.TestCase):
    client_cls = AWELClient
    region = "Zürich, Switzerland"
    variables = ["temperature", "relative_humidity"]
    variable_codes = ["temperature", "humidity"]
    start_date = "2022-03-22"
    end_date = "2022-03-23"
    ts_df_args = [start_date, end_date]


class IEMBaseClientTest(BaseClientTest):
    region = "Vermont"
    start_date = "2022-03-22"
    end_date = "2022-03-23"
    ts_df_args = [start_date, end_date]


class ASOSOneMinIEMClientTest(IEMBaseClientTest, unittest.TestCase):
    client_cls = ASOSOneMinIEMClient
    variable_codes = ["tmpf", "pres1"]


class METARASOSSIEMClientTest(IEMBaseClientTest, unittest.TestCase):
    client_cls = METARASOSIEMClient
    variable_codes = ["tmpf", "mslp"]


class MeteocatClientTest(APIKeyHeaderClientTest, unittest.TestCase):
    client_cls = MeteocatClient
    region = "Conca de Barberà"
    api_key = os.environ["METEOCAT_API_KEY"]
    variable_codes = [32, 34]
    start_date = "2022-03-22"
    end_date = "2022-03-23"
    ts_df_args = [start_date, end_date]


class MeteoSwissClientTest(BaseClientTest, unittest.TestCase):
    client_cls = MeteoSwissClient
    region = "Pully, Switzerland"
    variable_codes = ["tre200s0", "prestas0"]
    start_date = "2022-03-22"
    end_date = "2022-03-23"
    ts_df_args = [start_date, end_date]


class NetatmoClientTest(OAuth2ClientTest, unittest.TestCase):
    client_cls = NetatmoClient
    region = "Passanant i Belltall"
    client_id = os.environ["NETATMO_CLIENT_ID"]
    client_secret = os.environ["NETATMO_CLIENT_SECRET"]
    token = {"access_token": os.environ["NETATMO_ACCESS_TOKEN"]}
    # token = None
    variables = ["temperature", "relative_humidity"]
    variable_codes = ["temperature", "humidity"]
    start_date = "2024-12-22"
    end_date = "2024-12-23"
    ts_df_args = [start_date, end_date]

    # def setUp(self):
    #     with requests_mock.Mocker() as m:
    #         m.post(
    #             netatmo.OAUTH2_TOKEN_ENDPOINT,
    #             json={"token_type": "bearer", "access_token": "abcd"},
    #         )
    #         super().setUp()

    @pook.on
    def test_stations(self):
        with open(path.join(tests_data_dir, "netatmo-stations.json")) as src:
            pook.get(
                "https://api.netatmo.com/api/getpublicdata?lon_sw=1.1635994&"
                "lat_sw=41.48811&lon_ne=1.2635994000000002&lat_ne=41.58811",
                response_json=json.load(src),
            )
        super().test_stations()

    @pook.on
    def test_time_series(self):
        with open(path.join(tests_data_dir, "netatmo-time-series.json")) as src:
            pook.get(
                "https://api.netatmo.com/api/getmeasure?type=temperature%2Chumidity"
                "&scale=30min&limit=1024&optimize=True&real_time=False&"
                "device_id=70%3Aee%3A50%3A74%3A2a%3Aba&"
                "module_id=02%3A00%3A00%3A73%3Ae0%3A7e&"
                "date_begin=1734825600.0&date_end=1734912000.0",
                response_json=json.load(src),
            )
        super().test_time_series()


class GHCNHourlyClientTest(BaseClientTest, unittest.TestCase):
    client_cls = GHCNHourlyClient
    region = "Pully, Switzerland"
    variable_codes = ["temperature", "relative_humidity"]
    start_date = "2022-03-22"
    end_date = "2022-03-23"
    ts_df_args = [start_date, end_date]

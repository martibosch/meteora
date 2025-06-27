"""Tests for Meteora."""

import json
import logging as lg
import os
import tempfile
import unittest
from os import path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import pandas as pd
import pook
import pytest
import xarray as xr
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

from meteora import qc, settings, utils
from meteora.clients import (
    AemetClient,
    AgrometeoClient,
    ASOSOneMinIEMClient,
    GHCNHourlyClient,
    METARASOSIEMClient,
    MeteocatClient,
    MetOfficeClient,
    NetatmoClient,
)
from meteora.mixins import StationsEndpointMixin, VariablesEndpointMixin

tests_dir = "tests"
tests_data_dir = path.join(tests_dir, "data")


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


def test_utils():
    # geo utils
    # dms to dd
    dms_ser = pd.Series(["413120N"])
    dd_ser = utils.dms_to_decimal(dms_ser)
    assert is_numeric_dtype(dd_ser)

    # time series utils
    # long to wide
    ts_df = pd.read_csv(
        path.join(tests_data_dir, "ts-df.csv"),
        index_col=["station_id", "time"],
        parse_dates=True,
        date_format="%Y-%m-%d %H:%M:%S",
    )
    wide_ts_df = utils.long_to_wide(ts_df)
    # test wide data frame form
    assert isinstance(wide_ts_df.columns, pd.MultiIndex)
    assert isinstance(wide_ts_df.index, pd.DatetimeIndex)
    # with only one variable, we should have only one column level
    wide_ts_df = utils.long_to_wide(ts_df, variables=["temperature"])
    assert len(wide_ts_df.columns.names) == 1
    assert isinstance(wide_ts_df.index, pd.DatetimeIndex)

    # long to cube (xvec)
    stations_gdf = gpd.read_file(path.join(tests_data_dir, "stations.gpkg")).set_index(
        settings.STATIONS_ID_COL
    )
    with pytest.raises(KeyError):
        # if stations_gdf does not cover all stations in ts_df a KeyError is also raised
        utils.long_to_cube(ts_df, stations_gdf.iloc[:2])
        # attempting to convert from the wide form also raises a KeyError
        utils.wide_to_cube(wide_ts_df, stations_gdf)
    # test proper conversion
    ts_cube = utils.long_to_cube(ts_df, stations_gdf)
    # test an xarray dataset is returned
    assert isinstance(ts_cube, xr.Dataset)
    # test that the time column is in the coordinates
    assert ts_df.index.names[1] in ts_cube.coords
    # test that the variable columns are in the data_vars
    assert all([var in ts_cube.data_vars for var in ts_df.columns])
    # test that it has a dimension with geometry
    assert "geometry" in ts_cube.xvec.geom_coords
    assert "geometry" in ts_cube.xvec.geom_coords_indexed
    # test that there is a coordinate with the station ids and that all its values are
    # in the stations_gdf index
    assert settings.STATIONS_ID_COL in ts_cube.coords
    assert set(ts_cube[settings.STATIONS_ID_COL].values) <= set(stations_gdf.index)

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


def test_region_arg():
    # we will use Agrometeo (since it does not require API keys) to test the region arg
    nominatim_query = "Pully, Switzerland"
    gdf = ox.geocode_to_gdf(nominatim_query)
    with tempfile.TemporaryDirectory() as tmp_dir:
        filepath = path.join(tmp_dir, "foo.gpkg")
        gdf.to_file(filepath)
        for region in [nominatim_query, gdf, filepath]:
            client = AgrometeoClient(region=region)
            stations_gdf = client.stations_gdf
            assert len(stations_gdf) >= 1
    # now test naive geometries without providing CRS, so first ensure that we have them
    # in the same CRS as the client
    gdf = gdf.to_crs(client.CRS)
    for region in [gdf.total_bounds, gdf["geometry"].iloc[0]]:
        client = AgrometeoClient(region=region)
        stations_gdf = client.stations_gdf
        assert len(stations_gdf) >= 1


def test_qc():
    # read a wide ts df
    ts_df = pd.read_csv(
        path.join(tests_data_dir, "wide-ts-df.csv"), index_col="time", parse_dates=True
    )

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
        np.random.rand(len(ts_df.columns)) * 100, index=ts_df.columns
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


class BaseClientTest:
    client_cls = None
    region = None
    variables = ["temperature", "pressure"]
    variable_codes = None
    ts_df_args = None
    ts_df_kwargs = None

    def setUp(self):
        self.client = self.client_cls(region=self.region)

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
            # test that index is sorted (note that we need to test it as a multi-index
            # because otherwise the time index alone is not unique in long data frames
            assert ts_df.index.is_monotonic_increasing
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


class MetOfficeClientTest(APIKeyParamClientTest, unittest.TestCase):
    client_cls = MetOfficeClient
    region = "Edinburgh"
    api_key = os.environ["METOFFICE_API_KEY"]
    variable_codes = ["T", "P"]


class NetatmoClientTest(OAuth2ClientTest, unittest.TestCase):
    client_cls = NetatmoClient
    region = "Passanant i Belltall"
    client_id = os.environ["NETATMO_CLIENT_ID"]
    client_secret = os.environ["NETATMO_CLIENT_SECRET"]
    token = {"access_token": os.environ["NETATMO_ACCESS_TOKEN"]}
    # token = None
    variables = ["temperature", "water_vapour"]
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

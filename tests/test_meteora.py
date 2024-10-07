"""Tests for Meteora."""

import logging as lg
import os
import tempfile
import unittest
from os import path

import osmnx as ox
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

from meteora import settings, utils
from meteora.clients import (
    AemetClient,
    AgrometeoClient,
    ASOSOneMinIEMClient,
    METARASOSIEMClient,
    MeteocatClient,
    MetOfficeClient,
)
from meteora.mixins import AllStationsEndpointMixin, VariablesEndpointMixin


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
    # dms to dd
    dms_ser = pd.Series(["413120N"])
    dd_ser = utils.dms_to_decimal(dms_ser)
    assert is_numeric_dtype(dd_ser)

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
        if isinstance(self.client, AllStationsEndpointMixin):
            stations_gdf = self.client.stations_gdf
            assert len(stations_gdf) >= 1

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
            assert len(ts_df.index.get_level_values(0).unique()) == len(
                self.client.stations_gdf
            )
            # TODO: use "time" as `level` arg?
            assert is_datetime64_any_dtype(ts_df.index.get_level_values(1))
            # test that index is sorted (note that we need to test it as a multi-index
            # because otherwise the time index alone is not unique in long data frames
            assert ts_df.index.is_monotonic_increasing


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


class AemetClientTest(APIKeyParamClientTest, unittest.TestCase):
    client_cls = AemetClient
    region = "Catalunya"
    api_key = os.environ["AEMET_API_KEY"]
    variable_codes = ["ta", "pres"]

    def test_time_series(self):
        self.client.get_ts_df(self.variables)
        # ACHTUNG: for some reason (internal to Aemet's API), we get more stations from
        # the stations endpoint than from the data endpoint, so the assertions of the
        # `test_time_series` method would fail


class AgrometeoClientTest(BaseClientTest, unittest.TestCase):
    client_cls = AgrometeoClient
    region = "Pully, Switzerland"
    variable_codes = [1, 18]
    start_date = "2022-03-22"
    end_date = "2022-03-23"
    ts_df_args = [start_date, end_date]


@unittest.skip("Prevent testing abstract IEM Client")
class IEMBaseClientTest(BaseClientTest, unittest.TestCase):
    region = "Vermont"
    start_date = "2022-03-22"
    end_date = "2022-03-23"
    ts_df_args = [start_date, end_date]


class ASOSOneMinIEMClientTest(IEMBaseClientTest):
    client_cls = ASOSOneMinIEMClient
    variable_codes = ["tmpf", "pres1"]


class METARASOSSIEMClientTest(IEMBaseClientTest):
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

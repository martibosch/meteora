[![PyPI version fury.io](https://badge.fury.io/py/meteora.svg)](https://pypi.python.org/pypi/meteora)
[![Conda Version](https://img.shields.io/conda/vn/conda-forge/meteora.svg)](https://anaconda.org/conda-forge/meteora)
[![Documentation Status](https://readthedocs.org/projects/meteora/badge/?version=latest)](https://meteora.readthedocs.io/en/latest/?badge=latest)
[![tests](https://github.com/martibosch/meteora/actions/workflows/tests.yml/badge.svg)](https://github.com/martibosch/meteora/blob/main/.github/workflows/tests.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/martibosch/meteora/main.svg)](https://results.pre-commit.ci/latest/github/martibosch/meteora/main)
[![codecov](https://codecov.io/gh/martibosch/meteora/graph/badge.svg?token=smWkIfB7mM)](https://codecov.io/gh/martibosch/meteora)
[![GitHub license](https://img.shields.io/github/license/martibosch/meteora.svg)](https://github.com/martibosch/meteora/blob/main/LICENSE)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/martibosch/meteora/HEAD?labpath=docs%2Fuser-guide%2Fasos-example.ipynb)

# Meteora

Pythonic interface to access observations from meteorological stations. Key features:

- easily stream meteorological observations [from multiple providers, from global (e.g., GHCNh) and regional (e.g., MetOffice) networks to citizen weather stations (e.g., Netatmo)](https://meteora.readthedocs.io/en/latest/supported-providers.html) into pandas data frames.
- user-friendly arguments to filter data by region, variables or date ranges.
- request and download caching with [requests-cache](https://github.com/requests-cache/requests-cache) and [pooch](https://github.com/fatiando/pooch) to avoid re-downloading data and help bypassing API limits.

## Overview

Meteora provides a set of provider-specific clients to get observations from meteorological stations. For instance, it can be used to stream data from [the Global Historical Climatology Network hourly (GHCNh)](https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly) into a pandas data frame:

```python
from meteora.clients import GHCNHourlyClient

region = "Canton de Vaud, Switzerland"
variables = ["temperature", "precipitation", "surface_wind_speed"]
start = "12-11-2021"
end = "12-12-2021"

client = GHCNHourlyClient(region)
ts_df = client.get_ts_df(variables, start, end)
ts_df.head()
```

```
[########################################] | 100% Completed | 925.68 ms
```

| station_id  | time                | temperature | precipitation | surface_wind_speed |
| ----------- | ------------------- | ----------- | ------------- | ------------------ |
| SZI0000LSMP | 2021-12-11 00:20:00 | 2.0         | NaN           | 4.6                |
|             | 2021-12-11 00:50:00 | 2.0         | NaN           | 5.1                |
|             | 2021-12-11 01:20:00 | 2.0         | NaN           | 4.6                |
|             | 2021-12-11 01:50:00 | 2.0         | NaN           | 3.6                |
|             | 2021-12-11 02:20:00 | 2.0         | NaN           | 4.6                |

We can also get the station locations using the `stations_gdf` property:

```python
import contextily as cx

ax = client.stations_gdf.assign(
    T_mean=ts_df.groupby("station_id")["temperature"].mean()
).plot(
    "T_mean",
    cmap="winter",
    legend=True,
    legend_kwds={"label": "$\overline{T} \; [\circ C]$", "shrink": 0.5},
)
cx.add_basemap(ax, crs=client.stations_gdf.crs, attribution=False)
```

![vaud-stations-t-mean](https://github.com/martibosch/meteora/raw/main/docs/figures/vaud-stations-t-mean.png)

*(C) OpenStreetMap contributors, Tiles style by Humanitarian OpenStreetMap Team hosted by OpenStreetMap France*

See [the user guide](https://meteora.readthedocs.io/en/latest/user-guide.html) for more details about the features of Meteora as well as the [list of supported providers](https://meteora.readthedocs.io/en/latest/supported-providers.html).

## Installation

The easiest way to install Meteora is with conda/mamba:

```bash
conda install -c conda-forge meteora
```

Alternatively, if [geopandas dependencies are installed correctly](https://geopandas.org/en/latest/getting_started/install.html), you can install Meteora using pip:

```bash
pip install meteora
```

## See also

Meteora intends to provide a unified way to access data from meteorological stations from multiple providers. The following libraries provide access to data from a specific provider:

- [martibosch/agrometeo-geopy](https://github.com/martibosch/agrometeo-geopy)
- [martibosch/netatmo-geopy](https://github.com/martibosch/netatmo-geopy)

Eventually these packages will be fully integrated into Meteora.

## Acknowledgements

- The logging system is based on code from [gboeing/osmnx](https://github.com/gboeing/osmnx).
- This package was created with the [martibosch/cookiecutter-geopy-package](https://github.com/martibosch/cookiecutter-geopy-package) project template.
- With the support of the École Polytechnique Fédérale de Lausanne (EPFL).

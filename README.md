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

- easily stream meteorological observations [from multiple providers, from global (e.g., Global Historical Climatology Network hourly (GHCNh)) and regional (e.g., MetOffice) networks to citizen weather stations (e.g., Netatmo)](https://meteora.readthedocs.io/en/latest/supported-providers.html) into pandas data frames.
- user-friendly arguments to filter data by region, variables or date ranges.
- request and download caching with [requests-cache](https://github.com/requests-cache/requests-cache) and [pooch](https://github.com/fatiando/pooch) to avoid re-downloading data and help bypassing API limits.

## Overview

Meteora provides a set of provider-specific clients to get observations from meteorological stations. For instance, it can be used to stream [the one-minute ASOS data](https://madis.ncep.noaa.gov/madis_OMO.shtml) from the [Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu/request/asos/1min.phtml) into a pandas data frame:

```python
from meteora.clients import GHCNHourlyClient

region = "Davos, Switzerland"
variables = ["temperature", "precipitation", "surface_wind_speed"]
start = "12-11-2021"
end = "12-12-2021"

client = GHCNHourlyClient(region)
ts_df = client.get_ts_df(variables, start, end)
ts_df.head()
```

```
[########################################] | 100% Completed | 16.94 s
```

<div>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th></th>
      <th>temperature</th>
      <th>precipitation</th>
      <th>surface_wind_speed</th>
    </tr>
    <tr>
      <th>station_id</th>
      <th>time</th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th rowspan="5" valign="top">SZM00006784</th>
      <th>2021-12-11 00:00:00</th>
      <td>-4.7</td>
      <td>0.0</td>
      <td>5.1</td>
    </tr>
    <tr>
      <th>2021-12-11 01:00:00</th>
      <td>-4.8</td>
      <td>0.0</td>
      <td>5.1</td>
    </tr>
    <tr>
      <th>2021-12-11 02:00:00</th>
      <td>-4.8</td>
      <td>0.0</td>
      <td>3.6</td>
    </tr>
    <tr>
      <th>2021-12-11 03:00:00</th>
      <td>-4.8</td>
      <td>0.0</td>
      <td>3.6</td>
    </tr>
    <tr>
      <th>2021-12-11 04:00:00</th>
      <td>-4.7</td>
      <td>0.0</td>
      <td>3.1</td>
    </tr>
  </tbody>
</table>
</div>

We can also get the station locations using the `stations_gdf` property:

```python
import contextily as cx

ax = client.stations_gdf.plot()
cx.add_basemap(ax, crs=client.stations_gdf.crs, attribution=False)
```

![davos-stations](https://github.com/martibosch/meteora/raw/main/docs/figures/davos-stations.png)

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

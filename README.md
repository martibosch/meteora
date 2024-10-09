[![PyPI version fury.io](https://badge.fury.io/py/meteora.svg)](https://pypi.python.org/pypi/meteora)
[![Documentation Status](https://readthedocs.org/projects/meteora/badge/?version=latest)](https://meteora.readthedocs.io/en/latest/?badge=latest)
[![tests](https://github.com/martibosch/meteora/actions/workflows/tests.yml/badge.svg)](https://github.com/martibosch/meteora/blob/main/.github/workflows/tests.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/martibosch/meteora/main.svg)](https://results.pre-commit.ci/latest/github/martibosch/meteora/main)
[![codecov](https://codecov.io/gh/martibosch/meteora/graph/badge.svg?token=smWkIfB7mM)](https://codecov.io/gh/martibosch/meteora)
[![GitHub license](https://img.shields.io/github/license/martibosch/meteora.svg)](https://github.com/martibosch/meteora/blob/main/LICENSE)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/martibosch/meteora/HEAD?labpath=docs%2Fuser-guide%2Fasos-example.ipynb)

# Meteora

Pythonic interface to access data from meteorological stations. Key features:

- easily stream data [from multiple providers (e.g., Automated Surface/Weather Observing Systems (ASOS/AWOS), MetOffice...)](https://meteora.readthedocs.io/en/latest/supported-providers.html) into pandas data frames.
- user-friendly arguments to filter data by region, variables or date ranges.
- request caching with [requests-cache](https://github.com/requests-cache/requests-cache) to avoid re-downloading data and help bypassing API limits.

## Overview

Meteora provides a set of provider-specific clients to get observations from meteorological stations. For instance, it can be used to stream [the one-minute ASOS data](https://madis.ncep.noaa.gov/madis_OMO.shtml) from the [Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu/request/asos/1min.phtml) into a pandas data frame:

```python
from meteora.clients import ASOSOneMinIEMClient

region = "Oregon"
variables = ["temperature", "pressure", "precipitation", "surface_wind_speed"]
start = "2021-08-13"
end = "2021-08-16"

client = ASOSOneMinIEMClient(region=region)
ts_df = client.get_ts_df(variables, start=start, end=end)
ts_df.head()
```

<div>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th></th>
      <th>temperature</th>
      <th>pressure</th>
      <th>precipitation</th>
      <th>surface_wind_speed</th>
    </tr>
    <tr>
      <th>station</th>
      <th>valid(UTC)</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th rowspan="5" valign="top">AST</th>
      <th>2021-08-13 00:00:00</th>
      <td>68.0</td>
      <td>29.942</td>
      <td>0.0</td>
      <td>10.0</td>
    </tr>
    <tr>
      <th>2021-08-13 00:01:00</th>
      <td>67.0</td>
      <td>29.942</td>
      <td>0.0</td>
      <td>10.0</td>
    </tr>
    <tr>
      <th>2021-08-13 00:02:00</th>
      <td>67.0</td>
      <td>29.942</td>
      <td>0.0</td>
      <td>10.0</td>
    </tr>
    <tr>
      <th>2021-08-13 00:03:00</th>
      <td>67.0</td>
      <td>29.942</td>
      <td>0.0</td>
      <td>9.0</td>
    </tr>
    <tr>
      <th>2021-08-13 00:04:00</th>
      <td>68.0</td>
      <td>29.942</td>
      <td>0.0</td>
      <td>8.0</td>
    </tr>
  </tbody>
</table>
</div>

We can also get the station locations using the `stations_gdf` property:

```python
import contextily as cx

ax = client.stations_gdf.plot()
cx.add_basemap(ax, crs=client.stations_gdf.crs)
```

![oregon-stations](https://github.com/martibosch/meteora/raw/main/docs/figures/oregon-stations.png)

See [the user guide](https://meteora.readthedocs.io/en/latest/user-guide.html) for more details about the features of Meteora as well as the [list of supported providers](https://meteora.readthedocs.io/en/latest/supported-providers.html).

## Installation

Although Meteora is not available in conda-forge yet (hopefully will be soon), it can be installed using conda/mamba and pip as follows:

```bash
# install GDAL-based requirements
conda install -c conda-forge contextily geopandas osmnx
# install Meteora
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

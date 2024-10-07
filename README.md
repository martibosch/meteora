[![PyPI version fury.io](https://badge.fury.io/py/meteora.svg)](https://pypi.python.org/pypi/meteora)
[![Documentation Status](https://readthedocs.org/projects/meteora/badge/?version=latest)](https://meteora.readthedocs.io/en/latest/?badge=latest)
[![CI/CD](https://github.com/martibosch/meteora/actions/workflows/dev.yml/badge.svg)](https://github.com/martibosch/meteora/blob/main/.github/workflows/dev.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/martibosch/meteora/main.svg)](https://results.pre-commit.ci/latest/github/martibosch/meteora/main)
[![codecov](https://codecov.io/gh/martibosch/meteora/branch/main/graph/badge.svg?token=hKoSSRn58a)](https://codecov.io/gh/martibosch/meteora)
[![GitHub license](https://img.shields.io/github/license/martibosch/meteora.svg)](https://github.com/martibosch/meteora/blob/main/LICENSE)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/martibosch/meteora/HEAD?labpath=docs%2Fuser-guide%2Fagrometeo.ipynb)

# Meteora

Pythonic interface to access data from meteorological stations

## Installation

Although meteora is not available in PyPI and conda-forge yet (hopefully will be soon), it can be installed using conda/mamba and pip as follows:

```bash
# install GDAL-based requirements
conda install -c conda-forge contextily geopandas osmnx
# install meteora from GitHub
pip install https://github.com/martibosch/meteora/archive/main.zip
```

## Overview

This library provides a set of provider-specific clients to get observations from meteorological stations.

```python
from meteora.clients import agrometeo

start_date = "2021-08-13"
end_date = "2021-08-16"

client = agrometeo.AgrometeoClient(region="Canton de Genève")
ts_df = client.get_ts_df(start_date=start_date, end_date=end_date)
ts_df.head()
```

<div>
    <div class="wy-table-responsive"><table border="1" class="dataframe docutils">
            <thead>
                <tr style="text-align: right;">
                    <th>name</th>
                    <th>DARDAGNY</th>
                    <th>LA-PLAINE</th>
                    <th>SATIGNY</th>
                    <th>PEISSY</th>
                    <th>ANIERES</th>
                    <th>LULLY</th>
                    <th>LULLIER</th>
                    <th>BERNEX</th>
                    <th>TROINEX</th>
                    <th>MEINIER</th>
                </tr>
                <tr>
                    <th>time</th>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <th>2021-08-13 00:00:00</th>
                    <td>19.3</td>
                    <td>17.8</td>
                    <td>18.5</td>
                    <td>17.9</td>
                    <td>20.6</td>
                    <td>18.4</td>
                    <td>20.3</td>
                    <td>18.6</td>
                    <td>19.4</td>
                    <td>25.8</td>
                </tr>
                <tr>
                    <th>2021-08-13 00:10:00</th>
                    <td>19.6</td>
                    <td>17.9</td>
                    <td>18.4</td>
                    <td>17.7</td>
                    <td>20.0</td>
                    <td>18.3</td>
                    <td>19.6</td>
                    <td>18.7</td>
                    <td>19.1</td>
                    <td>28.6</td>
                </tr>
                <tr>
                    <th>2021-08-13 00:20:00</th>
                    <td>19.0</td>
                    <td>17.7</td>
                    <td>18.2</td>
                    <td>17.6</td>
                    <td>19.4</td>
                    <td>18.4</td>
                    <td>19.1</td>
                    <td>18.7</td>
                    <td>19.2</td>
                    <td>24.1</td>
                </tr>
                <tr>
                    <th>2021-08-13 00:30:00</th>
                    <td>18.3</td>
                    <td>18.0</td>
                    <td>18.1</td>
                    <td>17.4</td>
                    <td>19.1</td>
                    <td>18.3</td>
                    <td>19.1</td>
                    <td>18.6</td>
                    <td>18.9</td>
                    <td>22.5</td>
                </tr>
                <tr>
                    <th>2021-08-13 00:40:00</th>
                    <td>18.7</td>
                    <td>18.0</td>
                    <td>18.1</td>
                    <td>17.6</td>
                    <td>19.1</td>
                    <td>18.0</td>
                    <td>19.0</td>
                    <td>18.7</td>
                    <td>18.5</td>
                    <td>21.5</td>
                </tr>
            </tbody>
    </table></div>
    <p>5 rows × 10 columns</p>
</div>

```python
ts_df.resample("H").mean().plot()
```

![Agrometeo time series plot](https://github.com/martibosch/meteora/raw/main/docs/figures/agrometeo-ts.png)

See [the user guide](https://meteora.readthedocs.io/en/latest/user-guide.html) for more details.

## See also

This library intends to provide a unified way to access data from meteorological stations from multiple providers. The following libraries provide access to data from a specific provider:

- [martibosch/agrometeo-geopy](https://github.com/martibosch/agrometeo-geopy)
- [martibosch/netatmo-geopy](https://github.com/martibosch/netatmo-geopy)

Eventually these packages will be fully integrated into meteora.

## Acknowledgements

- Many utils such as the requests cache mechanism or the logging system are based on code from [gboeing/osmnx](https://github.com/gboeing/osmnx).
- This package was created with the [martibosch/cookiecutter-geopy-package](https://github.com/martibosch/cookiecutter-geopy-package) project template.
- With the support of the École Polytechnique Fédérale de Lausanne (EPFL).

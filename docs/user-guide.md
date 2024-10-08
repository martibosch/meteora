# User guide

Meteora provides a set of provider-specific clients to get observations from meteorological stations. The list of supported providers is available at the [API reference page](https://meteora.readthedocs.io/en/latest/api.html#available-clients).

## Example notebooks

```{toctree}
---
hidden:
maxdepth: 1
---

user-guide/asos-example
```

- [ASOS example](https://meteora.readthedocs.io/en/latest/user-guide/asos-example.html)

## Selecting a region

All clients are instantiated with at least the `region` argument, which defines the spatial extent of the required data. The `region` argument can be either:

- A string with a place name (Nominatim query) to geocode.
- A sequence with the west, south, east and north bounds.
- A geometric object, e.g., shapely geometry, or a sequence of geometric objects. In such a case, the region will be passed as the `data` argument of the GeoSeries constructor.
- A geopandas geo-series or geo-data frame.
- A filename or URL, a file-like object opened in binary (`'rb'`) mode, or a `Path` object that will be passed to `geopandas.read_file`.

## Selecting variables

When accessing to time series data (e.g., the `get_ts_df` method of each client), the `variables` argument is used to select the variables to retrieve. The `variables` argument can be either:

a) a string or integer with variable name or code according to the provider's nomenclature, or
b) a string referring to essential climate variable (ECV) following the Meteora nomenclature, i.e., a string among:

```python
ECVS = [
    "precipitation",  # Precipitation
    "pressure",  # Pressure (surface)
    "surface_radiation_longwave",  # Surface radiation budget (longwave)
    "surface_radiation_shortwave",  # Surface radiation budget (shortwave)
    "surface_wind_speed",  # Surface wind speed
    "surface_wind_direction",  # Surface wind direction
    "temperature",  # Air temperature (usually at 2m above ground)
    "water_vapour",  # Water vapour/relative humidity
]
```

See the guidelines by the [World Meteorological Organization](https://public.wmo.int/en/programmes/global-climate-observing-system/essential-climate-variables) on ECVs for more information.

## Selecting date range

While some providers only allow access to the most recent data, e.g., latest 24 hours, others allow querying data for a specific date range. In the latter case, the `start` and `end` arguments can be used to select the date range, which can be any object that can be converted to a [pandas `Timestamp` object](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.Timestamp.html), i.e., a string, integer, float or a datetime object from the datetime module or numpy.

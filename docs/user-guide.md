# User guide

Meteora provides a set of provider-specific clients to get observations from meteorological stations. The list of supported providers is available at the [API reference page](https://meteora.readthedocs.io/en/latest/api.html#available-clients).

## Example notebooks

```{toctree}
---
hidden:
maxdepth: 1
---

user-guide/agrometeo
user-guide/meteocat
```

- [Agrometeo](https://meteora.readthedocs.io/en/latest/user-guide/agrometeo.html)
- [Meteocat](https://meteora.readthedocs.io/en/latest/user-guide/meteocat.html)

## Selecting a region

All clients are instantiated with at least the `region` argument, which defines the spatial extent of the required data. The `region` argument can be either:

- A string with a place name (Nominatim query) to geocode.
- A sequence with the west, south, east and north bounds.
- A geometric object, e.g., shapely geometry, or a sequence of geometric objects. In such a case, the region will be passed as the `data` argument of the GeoSeries constructor.
- A geopandas geo-series or geo-data frame.
- A filename or URL, a file-like object opened in binary (`'rb'`) mode, or a `Path` object that will be passed to `geopandas.read_file`.

## Selecting variables

When accessing to data (e.g., the `get_ts_df` method of each client), the `variable` argument is used to select the variable to retrieve. The `variables` argument can be either:

a) a string or integer with variable name or code according to the provider's nomenclature, or
b) a string referring to essential climate variable (ECV) following the meteora nomenclature, i.e., a string among:

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

# Clients

A **client** wraps a single data provider (a web API or a file source) behind a uniform interface: `stations_gdf`, `variables_df`, and `get_ts_df(variables, start, end)`, which returns a long-form `(station, time)`-indexed data frame with one column per variable. Meteora ships the clients below; this guide explains how they are composed so you can write your own.

| Client                        | Type                                  | Stations                | Variables      | Time series                                                     |
| ----------------------------- | ------------------------------------- | ----------------------- | -------------- | --------------------------------------------------------------- |
| AemetClient                   | JSON (BaseJSONClient)                 | All stations            | All variables  | Single endpoint with latest data only                           |
| AgrometeoClient               | JSON (BaseJSONClient)                 | All stations            | All variables  | By time, variable, and stations                                 |
| AWELClient                    | File (BaseFileClient)                 | -                       | -              | Monthly files                                                   |
| ASOSOneMinIEMClient           | Text (BaseTextClient) + stations file | All stations            | -              | By time, variable and stations                                  |
| GHCNHourlyClient              | File (BaseFileClient)                 | All stations            | -              | Yearly files by station                                         |
| METARASOSIEMClient            | Text (BaseTextClient) + stations file | All stations            | -              | By time, variable and stations                                  |
| MeteocatClient                | JSON (BaseJSONClient)                 | All stations            | All variables  | Daily endpoints by variable                                     |
| MeteoFranceObservationsClient | JSON/Text (low-level draft)           | Station list endpoint   | Hardcoded      | Point observations plus packaged real-time downloads (24h only) |
| MetNorwayFrostClient          | JSON (BaseJSONClient)                 | Frost sources in region | Frost elements | Single observations endpoint, chunked by source list            |
| MeteoSwissClient              | File (BaseFileClient)                 | All stations            | All variables  | Decade files plus recent file by station                        |
| NetatmoClient                 | JSON (BaseJSONClient)                 | By bounding box         | -              | By time, variable and stations (modules), with API limits       |

## Decision workflow

Answer these questions about your provider; each one points to the base class, mixin, attribute, or method you need.

**1 — In what form does the service return time series?** → base class

| Response                          | Base class       | You implement                           |
| --------------------------------- | ---------------- | --------------------------------------- |
| JSON                              | `BaseJSONClient` | `_ts_df_from_content(response_content)` |
| Plain text / CSV over HTTP        | `BaseTextClient` | `_ts_df_from_content(response_content)` |
| Downloadable files (pooch-cached) | `BaseFileClient` | `_ts_df_from_url(url, ts_params)`       |

**2 — How are stations and variables discovered?** → endpoint mixins

| Source                     | Mixin (+ method to implement)                             |
| -------------------------- | --------------------------------------------------------- |
| Stations from an endpoint  | `StationsEndpointMixin` (+ `_stations_df_from_content`)   |
| Variables from an endpoint | `VariablesEndpointMixin` (+ `_variables_df_from_content`) |
| Fixed, known variable set  | `VariablesHardcodedMixin` (+ `_variables_dict`)           |

If stations come from a file rather than the time-series endpoint (IEM, MeteoSwiss), point `_stations_endpoint` at that file and parse it the same way.

**3 — Does one request return everything, or must it be split?** → partition mixins

- One call returns all stations *and* variables → **no partition mixins**; override `_ts_df_from_endpoint` directly (or just `_ts_df_from_content` for a `BaseJSONClient`).
- Otherwise add one partition mixin per axis you must split on. See [Mixin roles](#mixin-roles) and [MRO order](#mro-order).

**4 — What timezone are the timestamps in, and are they naive or aware?** → the `TZ` attribute plus a datetime helper. See [Timezone handling](#timezone-handling).

**5 — Does the response include rows outside `[start, end]`?** (some APIs over-fetch by a day) → call `self._clip_time_range(ts_df, start, end)` in your public `get_ts_df`.

### What every client must define

Regardless of the mixins, every client sets these (most as plain class attributes pointing at module-level constants):

| Attribute / method                          | Purpose                                                                         |
| ------------------------------------------- | ------------------------------------------------------------------------------- |
| `X_COL`, `Y_COL`                            | Longitude / latitude column names in the stations data                          |
| `CRS`                                       | CRS of the station coordinates (e.g. `utils.LONLAT_CRS`)                        |
| `_stations_gdf_id_col`                      | Station-id column in the stations response                                      |
| `_ts_df_stations_id_col`, `_ts_df_time_col` | Station-id and time column/level in the parsed time series                      |
| `_variables_id_col`                         | Variable-id column                                                              |
| `_ecv_dict`                                 | Maps each ECV name (`settings.ECV_*`) to the provider's variable id             |
| `_ts_endpoint`                              | URL template, formatted with `ts_params` (`{station_id}`, `{period.year}`, …)   |
| `TZ`                                        | Timezone of the data source (e.g. `"UTC"` or `"Europe/Zurich"`)                 |
| `get_ts_df(variables, start, end, …)`       | Public entry point: builds args, calls `self._get_ts_df(...)`, optionally clips |

## Writing a custom client

Meteora uses a **cooperative `super()` chain** to compose time series fetching from independent mixins. Each partitioning mixin enriches `ts_params` with its own key(s) and passes the updated dict down to `super()._ts_df_from_endpoint()`. The chain terminates at the base client (`BaseFileClient` or `BaseJSONClient` / `BaseTextClient`), which formats the endpoint URL and fetches data. The base client also handles the cross-cutting steps for you: variable renaming, unit attachment, and making the returned time index timezone-aware (see [Timezone handling](#timezone-handling)).

### Mixin roles

| Mixin                        | Adds to `ts_params`     | Concat axis | Use when…                   |
| ---------------------------- | ----------------------- | ----------- | --------------------------- |
| `StationPartitionedTSMixin`  | `{"station_id": …}`     | rows        | one request per station     |
| `TimePartitionedTSMixin`     | `{"period": Timestamp}` | rows        | one request per time period |
| `VariablePartitionedTSMixin` | `{"variable_id": …}`    | columns     | one request per variable    |

### MRO order

List partitioning mixins **outermost first**, then the base client classes. Any ordering of the partitioning mixins produces the correct `(station, time) × variables` output structure, so choose the order that matches the API's natural granularity (coarsest partition first):

```python
class MyClient(
    <outer partition>,   # e.g. StationPartitionedTSMixin
    <inner partition>,   # e.g. TimePartitionedTSMixin
    StationsEndpointMixin,
    BaseFileClient,      # always terminates the super() chain
)
```

### `TimePartitionedTSMixin` and `_time_partition_freq`

Set `_time_partition_freq` to a pandas frequency string. The mixin snaps the requested start date to the beginning of the first period and generates a `{"period": Timestamp}` dict for each period. Reference period attributes directly in `_ts_endpoint`:

| Frequency | `_time_partition_freq` | Template example                                      |
| --------- | ---------------------- | ----------------------------------------------------- |
| Daily     | `"D"`                  | `…/{period.year}/{period.month:02d}/{period.day:02d}` |
| Monthly   | `"MS"`                 | `…/{period.year}{period.month:02d}.csv`               |
| Yearly    | `"YS"`                 | `…/{period.year}/data_{station_id}_{period.year}.csv` |

For non-standard periods (e.g. historical decades), override `_iter_time_partitions` to return a list of `{"period": value}` dicts where `value` can be any object referenceable in the template.

## Timezone handling

Timezone is **one class attribute plus a choice of helper — not a mixin** (it is orthogonal to the partition mixins). Three questions decide it:

**What timezone are the source's timestamps in?** Every client declares `TZ` with the source's IANA timezone name (e.g. `"UTC"` or `"Europe/Zurich"`). That alone takes care of the **output**: `BaseClient._get_ts_df` makes the returned time index timezone-aware in `TZ` automatically — naive source timestamps are *localized* to `TZ`, already-aware ones are *converted* to it, and string timestamps are coerced to datetime first. You write no timezone code in `_ts_df_from_content` / `_ts_df_from_url`.

**When building the request (or filtering), does the service speak naive or aware timestamps?** This picks the helper you apply to `start` / `end`:

- **Naive, in the service's local time** (typical for CSV/file providers with bare `dd.mm.yyyy HH:MM`) → `self._naive_datetime(start)`: a naive `Timestamp` on the service's own clock.
- **Aware / ISO-offset / Unix epoch / UTC date parts** → `self._localize_datetime(start)`: a timezone-aware `Timestamp` in `TZ`, which you then format (`.timestamp()` for Unix time, `.year` / `.strftime(...)` for date components).

**Does the response over-fetch the window?** → call `self._clip_time_range(ts_df, start, end)` in your public `get_ts_df`. It normalizes the bounds to `TZ`, is timezone-safe regardless of how the user passed `start` / `end`, and preserves the attached units — don't hand-roll a boolean mask.

| Service trait                             | What you do                                          |
| ----------------------------------------- | ---------------------------------------------------- |
| Timestamps in UTC                         | `TZ = "UTC"`                                         |
| Timestamps in a local timezone            | `TZ = "<IANA name>"`                                 |
| Request expects naive local time          | `_naive_datetime(start/end)` in `_ts_params`         |
| Request expects aware / epoch / UTC parts | `_localize_datetime(start/end)` in `_ts_params`      |
| Response over-fetches the window          | `_clip_time_range(ts_df, start, end)` in `get_ts_df` |

Helper summary: `_localize_datetime(value)` → aware `Timestamp` in `TZ` (naive localized, aware converted); `_naive_datetime(value)` → the same with the timezone dropped; `_clip_time_range(ts_df, start, end, *, inclusive="both")` → timezone-safe `[start, end]` selection that preserves `ts_df.attrs`.

### Overridable hooks

| Hook                                         | Purpose                                                          |
| -------------------------------------------- | ---------------------------------------------------------------- |
| `_iter_time_partitions(ts_params)`           | Custom period list (overrides `_time_partition_freq`)            |
| `_iter_station_partitions(ts_params)`        | Custom station iteration                                         |
| `_iter_variable_partitions(ts_params)`       | Custom variable iteration                                        |
| `_format_ts_endpoint(ts_params)`             | Custom URL formatting (e.g. case transforms)                     |
| `_ts_cache(ts_params)`                       | Per-request caching rule                                         |
| `_ts_query_params(ts_params)`                | HTTP query parameters for `EndpointRequestTSMixin`               |
| `_format_variable_ts_df(ts_df, variable_id)` | Post-process per-variable result                                 |
| `_ts_df_from_endpoint(ts_params)`            | Full override for non-standard logic (e.g. dask parallelisation) |

### Minimal example — file-based, station × year

```python
class MyClient(
    StationPartitionedTSMixin,
    TimePartitionedTSMixin,
    StationsEndpointMixin,
    VariablesHardcodedMixin,
    BaseFileClient,
):
    _time_partition_freq = "YS"
    _ts_endpoint = "https://example.com/data/{station_id}/{period.year}.csv"
    TZ = "UTC"  # source timestamps are UTC

    def _ts_cache(self, ts_params):
        return ts_params["period"].year != pd.Timestamp.now().year

    def _ts_df_from_url(self, url, ts_params):
        try:
            source = self._ts_source(url, ts_params)
        except requests.HTTPError:
            return pd.DataFrame()
        ts_df = pd.read_csv(source)
        # … parse, filter to ts_params["start"]/ts_params["end"], set index …
        return ts_df.set_index([self._ts_df_stations_id_col, self._ts_df_time_col])
```

### Minimal example — request-based, variable × day

```python
class MyClient(
    VariablePartitionedTSMixin,
    TimePartitionedTSMixin,
    StationsEndpointMixin,
    VariablesEndpointMixin,
    BaseJSONClient,
):
    _time_partition_freq = "D"
    _ts_endpoint = (
        "https://example.com/obs/{variable_id}"
        "/{period.year}/{period.month:02d}/{period.day:02d}"
    )

    def _ts_query_params(self, ts_params):
        return {}

    def _ts_df_from_content(self, response_content):
        # … parse JSON, return (station, time)-indexed Series …
```

### Single-endpoint clients

When the API returns all stations and variables in one call, no partitioning mixins are needed. Override `_ts_df_from_endpoint` directly (or implement `_ts_df_from_content` for `BaseJSONClient` subclasses). If the response carries timestamps in the provider's local time, set `TZ`; if it returns extra rows around the requested window, clip in `get_ts_df`:

```python
class MyClient(StationsEndpointMixin, VariablesEndpointMixin, BaseJSONClient):
    _ts_endpoint = "https://example.com/data"
    TZ = "Europe/Zurich"  # naive local timestamps -> localized to Zurich on output

    def _ts_params(self, variable_ids, start, end):
        # service speaks naive local time, so build naive local bounds
        start, end = self._naive_datetime(start), self._naive_datetime(end)
        return {"sensors": ",".join(variable_ids), "from": str(start), "to": str(end)}

    def _ts_df_from_content(self, response_content):
        # … parse and return (station, time)-indexed DataFrame …

    def get_ts_df(self, variables, start, end):
        ts_df = self._get_ts_df(variables, start, end)
        return self._clip_time_range(ts_df, start, end)  # API over-fetches a day
```

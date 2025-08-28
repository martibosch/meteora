# History

## [v0.8.0] - 2025-08-28

### :sparkles: New Features

- [`b6fc8eb`](https://github.com/martibosch/meteora/commit/b6fc8ebfbc7cc43093d5e16d7739a10ba2d09647) - add MeteoSwiss client *(commit by [@martibosch](https://github.com/martibosch))*
- [`ef006c5`](https://github.com/martibosch/meteora/commit/ef006c5e1b32b6dc1a9c776aec7cbf7331372638) - update/expand ECV dicts *(commit by [@martibosch](https://github.com/martibosch))*

### :bug: Bug Fixes

- [`52b874d`](https://github.com/martibosch/meteora/commit/52b874d12d12914b0528752779e87d9580addf2b) - do NOT add prev/next day in heatwaves *(commit by [@martibosch](https://github.com/martibosch))*

## [v0.7.0] - 2025-08-10

### :sparkles: New Features

- [`4c57dc1`](https://github.com/martibosch/meteora/commit/4c57dc1f03fa609f568021b5554bda5ea9a0ac29) - GHCNh nodata for region/period warning - TODO: global approach *(commit by [@martibosch](https://github.com/martibosch))*
- [`a851310`](https://github.com/martibosch/meteora/commit/a851310089b2befd72d8b340147ed8cec7c416c4) - NETATMO_ON_GET_ERROR setting *(commit by [@martibosch](https://github.com/martibosch))*
- [`9a5617a`](https://github.com/martibosch/meteora/commit/9a5617a3613de3fdad9fe039b64886490a537435) - heatwave detection *(commit by [@martibosch](https://github.com/martibosch))*
- [`9525f5e`](https://github.com/martibosch/meteora/commit/9525f5e20345a491e6a6cc01be16cbb1f78f77eb) - catch netatmo error code 9 *(commit by [@martibosch](https://github.com/martibosch))*

### :white_check_mark: Tests

- [`79da984`](https://github.com/martibosch/meteora/commit/79da9845c9df5f5e01e6e67826d0154b1f626bb8) - ensure elev > 1 so that elev adj tests pass *(commit by [@martibosch](https://github.com/martibosch))*

## [v0.6.0] - 2025-06-30

### :sparkles: New Features

- [`4290ec2`](https://github.com/martibosch/meteora/commit/4290ec2e8a451a38cf764a14b45d0c9e2c4e40e5) - **netatmo**: dont fetch token for cache, better API error handling *(commit by [@martibosch](https://github.com/martibosch))*
- [`1816790`](https://github.com/martibosch/meteora/commit/18167906c895a5826c2b9a318d2f3948f7bf1da3) - update GHCNh client to new station list csv format *(commit by [@martibosch](https://github.com/martibosch))*
- [`9390cee`](https://github.com/martibosch/meteora/commit/9390cee6d67050a7a33e18a47ff52d760497dd4e) - add station ids as dimensionless coords in vector data cubes *(commit by [@martibosch](https://github.com/martibosch))*
- [`89938d5`](https://github.com/martibosch/meteora/commit/89938d544b93b7fb43e8673baa4fc7f2a4f335c9) - added AWEL client *(commit by [@martibosch](https://github.com/martibosch))*

### :bug: Bug Fixes

- [`3a66ddf`](https://github.com/martibosch/meteora/commit/3a66ddf8390ce0d0764176a29b94ac52d7eff482) - filter ts_df date range using pd.Timestamp (also in Meteocat) *(commit by [@martibosch](https://github.com/martibosch))*
- [`b938939`](https://github.com/martibosch/meteora/commit/b9389396d615e9799a22de249877a206950ce79f) - correct axis aggregation in outlier detection *(commit by [@martibosch](https://github.com/martibosch))*

### :recycle: Refactors

- [`6f07086`](https://github.com/martibosch/meteora/commit/6f070860bb6615e2d125874e5303e163a731d7ad) - stations_gdf in BaseClient with \_stations_gdf_id_col attr *(commit by [@martibosch](https://github.com/martibosch))*

### :white_check_mark: Tests

- [`69ce3d7`](https://github.com/martibosch/meteora/commit/69ce3d7af592d43565ae25ed84ceb438bd833da8) - mock requests with pook also for AEMET *(commit by [@martibosch](https://github.com/martibosch))*

## [v0.5.0] - 2025-04-10

### :sparkles: New Features

- [`5df1c84`](https://github.com/martibosch/meteora/commit/5df1c84f98e276772a9886a0ab6e99f391d36b92) - use yearly ghcnh files with pandas (drop polars/pyarrow) *(commit by [@martibosch](https://github.com/martibosch))*

### :bug: Bug Fixes

- [`783c027`](https://github.com/martibosch/meteora/commit/783c027c3d9da8b62732bd7d43cde70d05fe4ad2) - dms to decimal conversion (for aemet) *(commit by [@martibosch](https://github.com/martibosch))*

### :wrench: Chores

- [`34d6684`](https://github.com/martibosch/meteora/commit/34d66849e5467f1dc93311b85229d23b57557990) - update project license in pyproject.toml *(commit by [@martibosch](https://github.com/martibosch))*

## [v0.4.1] - 2025-03-27

### :bug: Bug Fixes

- [`f8a1815`](https://github.com/martibosch/meteora/commit/f8a18152d5883cf5b8c2673b6758a52717004674) - utils tests for standardized time/station cols; no posargs *(commit by [@martibosch](https://github.com/martibosch))*

## [v0.4.0] - 2025-03-27

### :boom: BREAKING CHANGES

- due to [`efcb356`](https://github.com/martibosch/meteora/commit/efcb356c6af506537c3ea6336baf46e0f73f75e8) - stations gdf and ts df id col as abstract attrs and settings *(commit by [@martibosch](https://github.com/martibosch))*:

  stations gdf and ts df id col as abstract attrs and settings

- due to [`7466e5c`](https://github.com/martibosch/meteora/commit/7466e5c82045f87a93a07c029c185a6281b83e6f) - filter ts range in agrometeo - TODO: find a better approach *(commit by [@martibosch](https://github.com/martibosch))*:

  filter ts range in agrometeo - TODO: find a better approach

### :sparkles: New Features

- [`e29a4a2`](https://github.com/martibosch/meteora/commit/e29a4a2746b7684791434c201cb5f0b834e10ecf) - long_to_wide function for time series data frames in utils *(commit by [@martibosch](https://github.com/martibosch))*
- [`9d77eff`](https://github.com/martibosch/meteora/commit/9d77eff9ab897be9bf08c533c244ae652a2d62a8) - added `long_to_cube` utils function *(commit by [@martibosch](https://github.com/martibosch))*
- [`efcb356`](https://github.com/martibosch/meteora/commit/efcb356c6af506537c3ea6336baf46e0f73f75e8) - stations gdf and ts df id col as abstract attrs and settings *(commit by [@martibosch](https://github.com/martibosch))*
- [`5c5e69f`](https://github.com/martibosch/meteora/commit/5c5e69f8bf79f9b406beac9d8b35791f0885294b) - split Netatmo ts requests in time range to respect API limits *(commit by [@martibosch](https://github.com/martibosch))*
- [`deaf616`](https://github.com/martibosch/meteora/commit/deaf616b81eb892168897a4565160a9afc9907e2) - QC module plus Netatmo+QC example notebook *(commit by [@martibosch](https://github.com/martibosch))*
- [`fb3c78d`](https://github.com/martibosch/meteora/commit/fb3c78dca2182f541fd1a99a302c1bbbb3cd70a2) - netatmo progress_apply from init to stations_gdf, more logging *(commit by [@martibosch](https://github.com/martibosch))*

### :bug: Bug Fixes

- [`76473ae`](https://github.com/martibosch/meteora/commit/76473ae23b2d9a63dab2fce69f76b95c14ba4b8b) - pl set null invalid dates then ignore (avoid errors in ghcnh) *(commit by [@martibosch](https://github.com/martibosch))*
- [`a183f95`](https://github.com/martibosch/meteora/commit/a183f95a0dc6a2602841ffe2915ab20578ec3895) - drop stale osmnx import in base client *(commit by [@martibosch](https://github.com/martibosch))*
- [`7466e5c`](https://github.com/martibosch/meteora/commit/7466e5c82045f87a93a07c029c185a6281b83e6f) - filter ts range in agrometeo - TODO: find a better approach *(commit by [@martibosch](https://github.com/martibosch))*

### :recycle: Refactors

- [`9b60e79`](https://github.com/martibosch/meteora/commit/9b60e798b863ae51d9b71e39c64ae8f2e78f826a) - use `pd.DataFrame.unstack` in `long_to_wide` *(commit by [@martibosch](https://github.com/martibosch))*
- [`7fa3145`](https://github.com/martibosch/meteora/commit/7fa3145f6a1686c70a413f2b88f12a720d400044) - remove stale `NetatmoConnect.get` method *(commit by [@martibosch](https://github.com/martibosch))*

## [v0.3.0] - 2025-03-16

### :boom: BREAKING CHANGES

- due to [`7f30983`](https://github.com/martibosch/meteora/commit/7f3098346fd77c261465cebb3c9a19b2e739b6e3) - rename kws->kwargs, update docstrings and type annots *(commit by [@martibosch](https://github.com/martibosch))*:

  rename kws->kwargs, update docstrings and type annots

### :sparkles: New Features

- [`4ca51b0`](https://github.com/martibosch/meteora/commit/4ca51b073554d703bd2346e1f255ca0b48b56d07) - noaa/ghcnh client *(commit by [@martibosch](https://github.com/martibosch))*

### :bug: Bug Fixes

- [`e5c6b0f`](https://github.com/martibosch/meteora/commit/e5c6b0f2d539ff3b9b96e36e176ba20d55410af0) - drop optimize arg for netatmo, add missing docstring for ts *(commit by [@martibosch](https://github.com/martibosch))*
- [`1ebd514`](https://github.com/martibosch/meteora/commit/1ebd51473373b8bf1657e49dbc27f38c6723c2c1) - drop MetOffice `res_param` argument (API only supports hourly) *(commit by [@martibosch](https://github.com/martibosch))*

### :recycle: Refactors

- [`7f30983`](https://github.com/martibosch/meteora/commit/7f3098346fd77c261465cebb3c9a19b2e739b6e3) - rename kws->kwargs, update docstrings and type annots *(commit by [@martibosch](https://github.com/martibosch))*
- [`609131a`](https://github.com/martibosch/meteora/commit/609131a1e4e8bbf5d5987b017e519708295bc425) - rm stale Netatmo bounds code, real time param as bool *(commit by [@martibosch](https://github.com/martibosch))*
- [`d2161c4`](https://github.com/martibosch/meteora/commit/d2161c4caf8c36bc08dfa1d9d1f241a21d05e35c) - only one stations endpoint mixin *(commit by [@martibosch](https://github.com/martibosch))*
- [`ab2d50d`](https://github.com/martibosch/meteora/commit/ab2d50d7748d69deca171a7ea1fe1288491baa26) - type definitions in utils *(commit by [@martibosch](https://github.com/martibosch))*
- [`c58c320`](https://github.com/martibosch/meteora/commit/c58c32095318eb427e87eb28b261940334b4da28) - use separate (reusable) region mixin for base client *(commit by [@martibosch](https://github.com/martibosch))*

## [v0.2.0] - 2025-03-13

### :boom: BREAKING CHANGES

- due to [`826aeec`](https://github.com/martibosch/meteora/commit/826aeece13036addeedba39080326d39630dcd37) - add 3.13 support, drop python 3.9 support *(commit by [@martibosch](https://github.com/martibosch))*:

  add 3.13 support, drop python 3.9 support

### :sparkles: New Features

- [`19a450d`](https://github.com/martibosch/meteora/commit/19a450d7a4c7f9670bf496fe329073bb61cdb364) - netatmo client with mocking in tests *(commit by [@martibosch](https://github.com/martibosch))*
- [`826aeec`](https://github.com/martibosch/meteora/commit/826aeece13036addeedba39080326d39630dcd37) - add 3.13 support, drop python 3.9 support *(commit by [@martibosch](https://github.com/martibosch))*

### :recycle: Refactors

- [`1d446de`](https://github.com/martibosch/meteora/commit/1d446deebc22ce238d4e2ab5a416b9d5f9113d24) - fix comments on base client *(commit by [@martibosch](https://github.com/martibosch))*
- [`747471b`](https://github.com/martibosch/meteora/commit/747471b2ad7e82c0ae9cf56e1ce14594e5197c13) - separate `_ts_df_from_endpoint` method in base client *(commit by [@martibosch](https://github.com/martibosch))*

## [v0.1.1] - 2024-10-09

### :recycle: Refactors

- [`624cf9b`](https://github.com/martibosch/meteora/commit/624cf9b0e591f4fbcc376b5d323a823294d8f6fc) - hardcopy abstract attribute to drop better_abc requirement *(commit by [@martibosch](https://github.com/martibosch))*

## 0.1.0 (2023-04-18)

- First release on PyPI.
  \[v0.1.1\]: https://github.com/martibosch/meteora/compare/v0.1.0...v0.1.1
  \[v0.2.0\]: https://github.com/martibosch/meteora/compare/v0.1.1...v0.2.0
  \[v0.3.0\]: https://github.com/martibosch/meteora/compare/v0.2.0...v0.3.0
  \[v0.4.0\]: https://github.com/martibosch/meteora/compare/v0.3.0...v0.4.0
  \[v0.4.1\]: https://github.com/martibosch/meteora/compare/v0.4.0...v0.4.1
  \[v0.5.0\]: https://github.com/martibosch/meteora/compare/v0.4.1...v0.5.0
  \[v0.6.0\]: https://github.com/martibosch/meteora/compare/v0.5.0...v0.6.0
  \[v0.7.0\]: https://github.com/martibosch/meteora/compare/v0.6.0...v0.7.0
  \[v0.8.0\]: https://github.com/martibosch/meteora/compare/v0.7.0...v0.8.0

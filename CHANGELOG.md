# History

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

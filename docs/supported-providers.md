# Supported providers

The key characteristics of the supported providers can be found in the following table.

| Provider         | Region                | Access to historical data | Auth                    |
| ---------------- | --------------------- | ------------------------- | ----------------------- |
| AEMET            | :es: Spain            | :clock1: Latest 24h only  | :key: API key (free)    |
| Agrometeo        | Switzerland           | :white_check_mark: Yes    | :white_check_mark: None |
| ASOS 1-min (IEM) | :us: USA              | :white_check_mark: Yes    | :white_check_mark: None |
| ASOS/METAR (IEM) | :earth_africa: Global | :white_check_mark: Yes    | :white_check_mark: None |
| Meteocat         | Catalonia             | :white_check_mark: Yes    | :key: API key (free)    |
| MetOffice        | :uk: United Kingdom   | :clock1: Latest 24h only  | :key: API key (free)    |

See more details about how to use each provider in the respective sections below as well as in the [API documentation](https://meteora.readthedocs.io/en/latest/api.html#available-clients).

## AEMET

[AEMET](https://www.aemet.es) is the meteorological agency of the Spanish state. It provides [a REST API](https://opendata.aemet.es/centrodedescargas/inicio) to access its data. To use the AEMET API, you first need to have an API key. You can get one by registering at [opendata.aemet.es/centrodedescargas/obtencionAPIKey](https://opendata.aemet.es/centrodedescargas/obtencionAPIKey).

## Agrometeo

[Agrometeo](https://www.agrometeo.ch) is a Swiss meteorological service that provides weather data for agriculture, which can be accessed for free and without authentication.

## Iowa Environmental Mesonet (IEM)

The [Iowa Environmental Mesonet (IEM)](https://mesonet.agron.iastate.edu) provides access to a wide range of environmental data, including weather observations from the Automated Surface Observing System (ASOS) stations in the United States. The IEM provides two clients to access ASOS data: one for 1-minute data and another for METAR data. Both clients can be accessed without authentication.

## Meteocat

[Meteocat](https://www.meteo.cat) is the Catalan Meteorological Service. It provides a REST API to access its data. To use the Meteocat API, you first need to have an API key. You can get one by registering at [apidocs.meteocat.gencat.cat/section/informacio-general/plans-i-registre](https://apidocs.meteocat.gencat.cat/section/informacio-general/plans-i-registre). You can choose the "Accés ciutadà i administració" plan, which is free, or the paid "Accés professionals" plan. In both cases, you need to check the box "Dades de la XEMA" (automated weather stations) to get access to the data used in Meteora. You will then receive by mail the API key.

## MetOffice

[MetOffice](https://www.metoffice.gov.uk) is the United Kingdom (UK) national weather service. It provides a [DataPoint API](https://www.metoffice.gov.uk/services/data/datapoint) with access to a range of data including observations, forecasts, climate averages, and weather warnings. The API is free to use but [the free tier is limited to 5000 requests per day, and 100 requests per minute](https://www.metoffice.gov.uk/services/data/datapoint/terms-and-conditions---datapoint). The ["Getting Started" guide](https://www.metoffice.gov.uk/services/data/datapoint/getting-started) describes the steps required to get an API key.

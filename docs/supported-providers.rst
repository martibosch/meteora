Supported providers
===================

The key characteristics of the supported providers can be found in the following table.

================ ======================== ========================== =========================
Provider         Region                   Access to historical data  Auth
================ ======================== ========================== =========================
AEMET            |:es:| Spain             |:clock1:| Latest 24h only |:key:| API key (free)
Agrometeo        |:switzerland:|          |:white_check_mark:| Yes   |:white_check_mark:| None
                 Switzerland
ASOS 1-min (IEM) |:us:| USA               |:white_check_mark:| Yes   |:white_check_mark:| None
ASOS/METAR (IEM) |:earth_africa:| Global  |:white_check_mark:| Yes   |:white_check_mark:| None
AWEL             |:switzerland:| Zurich   |:white_check_mark:| Yes   |:white_check_mark:| None
GHCNh (NOAA)     |:earth_africa:| Global  |:white_check_mark:| Yes   |:white_check_mark:| None
Meteocat         Catalonia                |:white_check_mark:| Yes   |:key:| API key (free)
MetOffice        |:great_britain:| United |:clock1:| Latest 24h only |:key:| API key (free)
                 Kingdom
Netatmo          |:earth_africa:| Global  |:white_check_mark:| Yes   |:key:| API key (free)
================ ======================== ========================== =========================

See more details about how to use each provider in the respective sections below as well
as in the `API documentation
<https://meteora.readthedocs.io/en/latest/api.html#available-clients>`__.

AEMET
-----

`AEMET <https://www.aemet.es>`__ is the meteorological agency of the Spanish state. It
provides `a REST API <https://opendata.aemet.es/centrodedescargas/inicio>`__ to access
its data. To use the AEMET API, you first need to have an API key. You can get one by
registering at `opendata.aemet.es/centrodedescargas/obtencionAPIKey
<https://opendata.aemet.es/centrodedescargas/obtencionAPIKey>`__.

Agrometeo
---------

`Agrometeo <https://www.agrometeo.ch>`__ is a Swiss meteorological service that provides
weather data for agriculture, which can be accessed for free and without authentication.

Global Historical Climatology Network hourly (GHCNh)
----------------------------------------------------

The `Global Historical Climatology Network hourly (GHCNh)
<https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly>`__ is
a dataset of hourly surface weather observations from fixed, land-based stations from
numerous sources around the world. The GHCNh is managed by the National Oceanic and
Atmospheric Administration (NOAA) and can be accessed for free and without
authentication. Note that the same dataset is also provided at the daily and monthly
resolutions, however Meteora currently only supports the hourly dataset (since daily and
monthly aggregations can be easily computed from the hourly records).

Iowa Environmental Mesonet (IEM)
--------------------------------

The `Iowa Environmental Mesonet (IEM) <https://mesonet.agron.iastate.edu>`__ provides
access to a wide range of environmental data, including weather observations from the
Automated Surface Observing System (ASOS) stations in the United States. The IEM
provides two clients to access ASOS data: one for 1-minute data and another for METAR
data. Both clients can be accessed without authentication.

Meteocat
--------

`Meteocat <https://www.meteo.cat>`__ is the Catalan Meteorological Service. It provides
a REST API to access its data. To use the Meteocat API, you first need to have an API
key. You can get one by registering at
`apidocs.meteocat.gencat.cat/section/informacio-general/plans-i-registre
<https://apidocs.meteocat.gencat.cat/section/informacio-general/plans-i-registre>`__.
You can choose the “Accés ciutadà i administració” plan, which is free, or the paid
“Accés professionals” plan. In both cases, you need to check the box “Dades de la XEMA”
(automated weather stations) to get access to the data used in Meteora. You will then
receive by mail the API key.

MetOffice
---------

`MetOffice <https://www.metoffice.gov.uk>`__ is the United Kingdom (UK) national weather
service. It provides a `DataPoint API
<https://www.metoffice.gov.uk/services/data/datapoint>`__ with access to a range of data
including observations, forecasts, climate averages, and weather warnings. The API is
free to use but `the free tier is limited to 5000 requests per day, and 100 requests per
minute
<https://www.metoffice.gov.uk/services/data/datapoint/terms-and-conditions---datapoint>`__.
The `“Getting Started” guide
<https://www.metoffice.gov.uk/services/data/datapoint/getting-started>`__ describes the
steps required to get an API key.

Netatmo
-------

`Netatmo <https://www.netatmo.com>`__ is a manufacturer of smart home devices including
citizen weather stations (CWS). Their `Weather API
<https://dev.netatmo.com/apidocumentation/weather>`__ permits retrieving the
measurements of users who share it publicly, including temperature, humidity, pressure,
wind and precipitation. In order to access the data from Netatmo CWS, you need a client
ID and client secret, which can be obtained following the steps below:

1. If you do not have a Netatmo account, sign up at `auth.netatmo.com/access/signup
   <https://auth.netatmo.com/access/signup>`__.
2. If you do not have any app, you can create one from your account by navigating to
   `dev.netatmo.com/apps <https://dev.netatmo.com/apps>`__ and clicking "Create". As far
   as Meteora is concerned, this only serves to obtain a client ID and secret key, so
   you do not need to enter any specific information in "app name" and "description".
3. Once the app is created, save the generated "client ID" and "client secret" which
   will appear in the form below (entitled "App Technical Parameters"). You will need to
   provide them for the initialization of `meteora.clients.NetatmoClient`.

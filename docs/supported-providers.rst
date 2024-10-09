Supported providers
===================

The key characteristics of the supported providers can be found in the
following table.

+------------+-------------------+----------------------+----------------------+
| Provider   | Region            | Access to            | Auth                 |
|            |                   | historical data      |                      |
+============+===================+======================+======================+
| AEMET      | |:es:| Spain      | |:clock1:| Latest    | |:key:| API key      |
|            |                   | 24h only             | (free)               |
+------------+-------------------+----------------------+----------------------+
| Agrometeo  | |:switzerland:|   | |:white_check_mark:| | |:white_check_mark:| |
|            | Switzerland       | Yes                  | None                 |
+------------+-------------------+----------------------+----------------------+
| ASOS 1-min | |:us:| USA        | |:white_check_mark:| | |:white_check_mark:| |
| (IEM)      |                   | Yes                  | None                 |
+------------+-------------------+----------------------+----------------------+
| ASOS/METAR | |:earth_africa:|  | |:white_check_mark:| | |:white_check_mark:| |
| (IEM)      | Global            | Yes                  | None                 |
+------------+-------------------+----------------------+----------------------+
| Meteocat   | Catalonia         | |:white_check_mark:| | |:key:| API key      |
|            |                   | Yes                  | (free)               |
+------------+-------------------+----------------------+----------------------+
| MetOffice  | |:great_britain:| | |:clock1:| Latest    | |:key:| API key      |
|            | United Kingdom    | 24h only             | (free)               |
+------------+-------------------+----------------------+----------------------+

See more details about how to use each provider in the respective
sections below as well as in the `API
documentation <https://meteora.readthedocs.io/en/latest/api.html#available-clients>`__.

AEMET
-----

`AEMET <https://www.aemet.es>`__ is the meteorological agency of the
Spanish state. It provides `a REST
API <https://opendata.aemet.es/centrodedescargas/inicio>`__ to access
its data. To use the AEMET API, you first need to have an API key. You
can get one by registering at
`opendata.aemet.es/centrodedescargas/obtencionAPIKey <https://opendata.aemet.es/centrodedescargas/obtencionAPIKey>`__.

Agrometeo
---------

`Agrometeo <https://www.agrometeo.ch>`__ is a Swiss meteorological
service that provides weather data for agriculture, which can be
accessed for free and without authentication.

Iowa Environmental Mesonet (IEM)
--------------------------------

The `Iowa Environmental Mesonet
(IEM) <https://mesonet.agron.iastate.edu>`__ provides access to a wide
range of environmental data, including weather observations from the
Automated Surface Observing System (ASOS) stations in the United States.
The IEM provides two clients to access ASOS data: one for 1-minute data
and another for METAR data. Both clients can be accessed without
authentication.

Meteocat
--------

`Meteocat <https://www.meteo.cat>`__ is the Catalan Meteorological
Service. It provides a REST API to access its data. To use the Meteocat
API, you first need to have an API key. You can get one by registering
at
`apidocs.meteocat.gencat.cat/section/informacio-general/plans-i-registre <https://apidocs.meteocat.gencat.cat/section/informacio-general/plans-i-registre>`__.
You can choose the “Accés ciutadà i administració” plan, which is free,
or the paid “Accés professionals” plan. In both cases, you need to check
the box “Dades de la XEMA” (automated weather stations) to get access to
the data used in Meteora. You will then receive by mail the API key.

MetOffice
---------

`MetOffice <https://www.metoffice.gov.uk>`__ is the United Kingdom (UK)
national weather service. It provides a `DataPoint
API <https://www.metoffice.gov.uk/services/data/datapoint>`__ with
access to a range of data including observations, forecasts, climate
averages, and weather warnings. The API is free to use but `the free
tier is limited to 5000 requests per day, and 100 requests per
minute <https://www.metoffice.gov.uk/services/data/datapoint/terms-and-conditions---datapoint>`__.
The `“Getting Started”
guide <https://www.metoffice.gov.uk/services/data/datapoint/getting-started>`__
describes the steps required to get an API key.

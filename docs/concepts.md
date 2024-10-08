# Concepts

## What is Meteora

The aim of Meteora is to provide an unified Pythonic interface to access data from meteorological stations.

## Core components

### Client

Essentially, Meteora is a collection of clients, each specific to a providers. The role of the client is to query the different endpoints of the provider and return the data in the common format used by Meteora.

## Developing your own client

### Principles

#### Conceptual

As an open source library, Meteora intends to remove barriers to the access of meteorological observation data. Therefore, the following principles are considered in order to decide which providers are supported:

- **Transparency**: only providers that support access to *actual observation data* (i.e., measurements from meteorological stations) are supported, thus excluding providers with a free tier to access *modeled data* such as [openweather](https://openweathermap.org/api), [tomorrow.io](https://www.tomorrow.io/weather-api) or [meteomatics](https://www.meteomatics.com/en/weather-api).
- **Open access**: priority is given to implementing free endpoints

#### Technical

- All that can be standardized will be standardized, but all data is valuable, so we must allow the user to access it if desired.
- Minimize the number of queries, especially for metadata.

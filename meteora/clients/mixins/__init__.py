"""Mixins module."""

from meteora.clients.mixins.auth import APIKeyHeaderMixin, APIKeyParamMixin
from meteora.clients.mixins.stations import StationsEndpointMixin
from meteora.clients.mixins.time_series import (
    PartitionedTSMixin,
    StationPartitionedTSMixin,
    TimePartitionedTSMixin,
    VariablePartitionedTSMixin,
)
from meteora.clients.mixins.variables import (
    VariablesEndpointMixin,
    VariablesHardcodedMixin,
)

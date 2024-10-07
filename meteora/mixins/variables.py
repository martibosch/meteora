"""Variables mixins."""

import pandas as pd
from better_abc import abstract_attribute

# https://public.wmo.int/en/programmes/global-climate-observing-system/essential-climate-variables
ECVS = [
    "precipitation",
    "pressure",
    "surface_radiation_longwave",
    "surface_radiation_shortwave",
    "surface_wind_speed",
    "surface_wind_direction",
    "temperature",
    "water_vapour",
]


class VariablesMixin:
    """Variables Mixin."""

    @abstract_attribute
    def _variables_id_col(self):
        pass

    @abstract_attribute
    def _ecv_dict(self):
        pass

    def _process_variable_arg(self, variable):
        # process the variable arg
        # variable is a string that can be either:
        # a) a variable code according to the provider's nomenclature
        # b) an essential climate variable (ECV) following the meteora nomenclature
        if isinstance(variable, int) or variable.isdigit():
            # case a: if variable is an integer, assert that it is a valid variable code
            variable_id = int(variable)
            if variable_id not in self.variables_df[self._variables_id_col].values:
                raise ValueError(f"variable {variable} is not a valid variable id")
        elif variable in self.variables_df[self._variables_id_col].values:
            # still case a: if variable is a variable code, but it is a string - then,
            # just return it as it is
            return variable
        else:
            # case b: if variable is an ECV, it will be a key in the ECV_DICT so
            # the provider's variable code can be retrieved directly, otherwise we
            # assume that variable is a variable name (provider's nomenclature).
            variable_id = self._ecv_dict.get(variable, variable)
            # variable_code = self.variables_df.loc[
            #     self.variables_df[self._variables_label_col] == variable_name,
            #     self._variables_code_col,
            # ].item()

        return variable_id

    def _get_variable_ids(self, variables):
        """Given the `variables` argument, return a list of variable codes."""
        if not pd.api.types.is_list_like(variables):
            variables = [variables]
        return [self._process_variable_arg(variable) for variable in variables]


class VariablesHardcodedMixin(VariablesMixin):
    """Hardcoded variables mixin."""

    @abstract_attribute
    def _variables_dict(self):
        pass

    @abstract_attribute
    def _variables_label_col(self):
        pass

    @property
    def variables_df(self) -> pd.DataFrame:
        """Variables dataframe."""
        try:
            return self._variables_df
        except AttributeError:
            variables_df = pd.DataFrame(
                self._variables_dict.items(),
                columns=[self._variables_id_col, self._variables_label_col],
            )
            self._variables_df = variables_df
            return self._variables_df


class VariablesEndpointMixin(VariablesMixin):
    """Variables endpoint mixin."""

    @abstract_attribute
    def _variables_endpoint(self):
        pass

    @property
    def variables_df(self) -> pd.DataFrame:
        """Variables dataframe."""
        try:
            return self._variables_df
        except AttributeError:
            response_content = self._get_content_from_url(self._variables_endpoint)
            self._variables_df = self._variables_df_from_content(response_content)
            return self._variables_df

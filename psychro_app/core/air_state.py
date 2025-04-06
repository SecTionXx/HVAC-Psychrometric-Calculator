# psychro_app/core/air_state.py
from . import psychrolib_wrapper as psy_wrap
import logging

log = logging.getLogger(__name__)

class AirState:
    """Represents the thermodynamic state of moist air."""
    def __init__(self, pressure_pa: float, label: str = "State", **kwargs):
        """
        Initialize AirState. Requires pressure and exactly two other known properties.

        Args:
            pressure_pa (float): Atmospheric pressure in Pascals.
            label (str): An optional label for this state (e.g., "Outside Air").
            **kwargs: Exactly two known properties (e.g., tdb=25, rh=0.5).
                      Valid keys: 'tdb', 'rh', 'twb', 'w', 'tdp', 'h'.
                      RH should be provided as a fraction (0-1).
        """
        self.label = label
        self.pressure = pressure_pa
        self.tdb: float | None = None  # Dry Bulb Temp (°C)
        self.twb: float | None = None  # Wet Bulb Temp (°C)
        self.rh: float | None = None   # Relative Humidity (0-1)
        self.w: float | None = None    # Humidity Ratio (kg_water/kg_dry_air)
        self.h: float | None = None    # Specific Enthalpy (J/kg_dry_air)
        self.tdp: float | None = None  # Dew Point Temp (°C)
        self.v: float | None = None    # Specific Volume (m³/kg_dry_air)

        self.update(**kwargs) # Calculate all properties on init

    def update(self, **kwargs) -> bool:
        """
        Updates the air state properties based on new known inputs.
        Requires exactly two known properties passed as keyword arguments.
        Uses the pressure stored in the object.

        Args:
            **kwargs: Exactly two known properties (e.g., tdb=25, rh=0.5).

        Returns:
            True if update was successful and state is valid, False otherwise.
        """
        if not kwargs:
             log.warning(f"AirState '{self.label}' update called with no properties.")
             return self.is_valid() # Return current validity
        if len(kwargs) != 2:
             log.error(f"AirState '{self.label}' update requires exactly two known properties. Got: {kwargs.keys()}")
             self._invalidate_state() # Clear state if update is invalid
             return False

        log.info(f"Updating AirState '{self.label}' with {kwargs} at {self.pressure} Pa")
        all_props = psy_wrap.get_all_properties(self.pressure, **kwargs)

        if all_props:
            self.tdb = all_props.get('tdb')
            self.twb = all_props.get('twb')
            self.rh = all_props.get('rh')
            self.w = all_props.get('w')
            self.h = all_props.get('h')
            self.tdp = all_props.get('tdp')
            self.v = all_props.get('v')
            # self.pressure remains unchanged
            log.debug(f"AirState '{self.label}' updated successfully: {self}")
            return self.is_valid()
        else:
            log.error(f"Failed to calculate properties for AirState '{self.label}' with inputs {kwargs}")
            self._invalidate_state() # Clear state on calculation failure
            return False

    def _invalidate_state(self):
        """Sets all thermodynamic properties to None."""
        self.tdb = None
        self.twb = None
        self.rh = None
        self.w = None
        self.h = None
        self.tdp = None
        self.v = None

    def is_valid(self) -> bool:
        """Checks if essential properties have been calculated."""
        # Check if core properties needed for further calcs are non-None
        return all(p is not None for p in [self.tdb, self.w, self.h])

    def __str__(self) -> str:
        if not self.is_valid():
             return f"AirState '{self.label}' (Invalid/Not Calculated)"
        return (f"AirState '{self.label}': "
                f"Tdb={self.tdb:.1f}°C, RH={self.rh*100:.1f}%, "
                f"W={self.w*1000:.2f} g/kg, h={self.h/1000:.1f} kJ/kg, "
                f"Twb={self.twb:.1f}°C, Tdp={self.tdp:.1f}°C, v={self.v:.3f} m³/kg")

    def get_properties_dict(self) -> dict:
         """Returns properties as a dictionary for easy access (e.g., for tables)."""
         return {
             'label': self.label,
             'pressure_pa': self.pressure,
             'tdb_c': self.tdb,
             'twb_c': self.twb,
             'rh_frac': self.rh, # Keep RH as fraction internally maybe? Display layer converts.
             'rh_percent': self.rh * 100 if self.rh is not None else None,
             'w_kg_kg': self.w,
             'w_g_kg': self.w * 1000 if self.w is not None else None,
             'h_j_kg': self.h,
             'h_kj_kg': self.h / 1000 if self.h is not None else None,
             'tdp_c': self.tdp,
             'v_m3_kg': self.v,
             'is_valid': self.is_valid()
         }

    def get_display_value(self, prop_key: str, precision: int = 1) -> str:
        """Gets a formatted string for display, handling None."""
        props = self.get_properties_dict()
        value = props.get(prop_key)
        if value is None:
            return "N/A"
        try:
            # Format numeric values based on key hints
            if '_c' in prop_key or 'temp' in prop_key: # Temperatures
                return f"{value:.{precision}f}"
            elif 'percent' in prop_key: # RH %
                return f"{value:.{precision}f}"
            elif 'g_kg' in prop_key: # W g/kg
                return f"{value:.{precision+1}f}" # Usually need more precision
            elif 'kj_kg' in prop_key: # h kJ/kg
                 return f"{value:.{precision}f}"
            elif 'm3_kg' in prop_key: # v m3/kg
                 return f"{value:.{precision+2}f}" # Usually need more precision
            else:
                return str(value) # Fallback for non-numeric or unexpected keys
        except (TypeError, ValueError):
            return str(value) # Fallback if formatting fails
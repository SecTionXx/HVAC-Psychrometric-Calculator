# psychro_app/systems/ahu_model.py
from psychro_app.core.air_state import AirState
from psychro_app.processes import hvac_processes as hvac
import logging

log = logging.getLogger(__name__)

class AHUModel:
    def __init__(self, pressure_pa: float):
        self.pressure = pressure_pa
        self.states = {}
        self._reset_states()
        log.info(f"AHUModel initialized at {pressure_pa} Pa.")

    def _reset_states(self):
        self.states = {
            "OA": None,
            "RA": None,
            "MA": None,
            "CC_Out": None,
            "HC_Out": None, # Represents state after Heating OR after Reheat in cooling mode
            "HUM_Out": None, # State after Humidifier
            "SA": None, # Final Supply Air (after fan)
        }
        log.debug("AHU states reset.")

    def set_inlet_conditions(self, oa_tdb, oa_rh, ra_tdb, ra_rh) -> bool:
        """Set Outside Air and Return Air conditions. Returns True if successful."""
        self._reset_states() # Reset previous calculations when inputs change
        log.info(f"Setting AHU inlets: OA({oa_tdb=:.1f}, {oa_rh=:.2f}), RA({ra_tdb=:.1f}, {ra_rh=:.2f})")
        oa_state = AirState(pressure_pa=self.pressure, label="OA", tdb=oa_tdb, rh=oa_rh)
        ra_state = AirState(pressure_pa=self.pressure, label="RA", tdb=ra_tdb, rh=ra_rh)

        if oa_state.is_valid() and ra_state.is_valid():
            self.states["OA"] = oa_state
            self.states["RA"] = ra_state
            return True
        else:
            log.error("Failed to create valid OA or RA state from inputs.")
            self._reset_states() # Ensure clean state on failure
            return False

    def run_cooling_cycle(self, oa_mass_flow: float, ra_mass_flow: float,
                         cc_adp: float, cc_bf: float,
                         reheat_q_watts: float = 0,
                         humidifier_type: str = "None", # Ensure this parameter exists
                         humidifier_param: float = 0, # Ensure this parameter exists
                         fan_heat_watts: float = 0) -> bool:
        """
        Simulates AHU cooling cycle with optional reheat and humidification.
        Order: Mix -> Cool -> Reheat -> Humidify -> Fan
        """
        log.info("Running AHU Cooling Cycle simulation...")
        if not self.states.get("OA") or not self.states.get("RA"):
            log.error("Inlet conditions (OA, RA) must be set and valid.")
            return False

        total_flow = oa_mass_flow + ra_mass_flow
        if total_flow <= 1e-9: log.error("Total AHU flow must be positive."); return False

        # --- Process Steps ---
        current_state = self.states["OA"] # Starting point for checks

        # 1. Mixing
        self.states["MA"] = hvac.mix_air(self.states["OA"], oa_mass_flow, self.states["RA"], ra_mass_flow)
        if not self.states["MA"]: return False
        current_state = self.states["MA"]

        # 2. Cooling Coil
        self.states["CC_Out"] = hvac.cooling_coil_simplified(current_state, total_flow, cc_adp, cc_bf)
        if not self.states["CC_Out"]: return False
        current_state = self.states["CC_Out"]

        # 3. Reheat (If applicable) - uses HC_Out slot
        if reheat_q_watts > 0:
            self.states["HC_Out"] = hvac.sensible_heat(current_state, reheat_q_watts, total_flow)
            if not self.states["HC_Out"]: return False
            current_state = self.states["HC_Out"]
            log.info(f"Reheat applied: Q={reheat_q_watts} W")
        else:
            self.states["HC_Out"] = current_state # Pass through if no reheat

        # 4. Humidification (If applicable) - Choose type
        if humidifier_type == "Steam" and humidifier_param > 0:
            self.states["HUM_Out"] = hvac.steam_humidify(current_state, total_flow, humidifier_param)
            if not self.states["HUM_Out"]: return False
            current_state = self.states["HUM_Out"]
        elif humidifier_type == "Adiabatic" and humidifier_param > 0:
            self.states["HUM_Out"] = hvac.adiabatic_humidify(current_state, humidifier_param)
            if not self.states["HUM_Out"]: return False
            current_state = self.states["HUM_Out"]
        else:
             self.states["HUM_Out"] = current_state # Pass through if no humidification or param is zero

        # 5. Supply Fan Heat Gain
        if fan_heat_watts > 0:
            self.states["SA"] = hvac.sensible_heat(current_state, fan_heat_watts, total_flow)
            if not self.states["SA"]: return False
        else:
            self.states["SA"] = current_state # No fan heat

        log.info("AHU Cooling Cycle calculation completed.")
        return True

    def run_heating_cycle(self, oa_mass_flow: float, ra_mass_flow: float,
                         heating_q_sensible: float,
                         humidifier_type: str = "None", # Ensure this parameter exists
                         humidifier_param: float = 0, # Ensure this parameter exists
                         fan_heat_watts: float = 0) -> bool:
        """
        Simulates AHU heating cycle with optional humidification.
        Order: Mix -> Heat -> Humidify -> Fan (Cooling coil bypassed)
        """
        log.info("Running AHU Heating Cycle simulation...")
        if not self.states.get("OA") or not self.states.get("RA"):
             log.error("Inlet conditions (OA, RA) must be set and valid."); return False

        total_flow = oa_mass_flow + ra_mass_flow
        if total_flow <= 1e-9: log.error("Total AHU flow must be positive."); return False

        # --- Process Steps ---
        current_state = self.states["OA"]

        # 1. Mixing
        self.states["MA"] = hvac.mix_air(self.states["OA"], oa_mass_flow, self.states["RA"], ra_mass_flow)
        if not self.states["MA"]: return False
        current_state = self.states["MA"]

        # 2. Cooling Coil (Bypassed)
        self.states["CC_Out"] = current_state

        # 3. Heating Coil
        if heating_q_sensible > 0:
             self.states["HC_Out"] = hvac.sensible_heat(current_state, heating_q_sensible, total_flow)
             if not self.states["HC_Out"]: return False
             current_state = self.states["HC_Out"]
        else:
             self.states["HC_Out"] = current_state # Pass through if no heating

        # 4. Humidification (If applicable) - Choose type
        if humidifier_type == "Steam" and humidifier_param > 0:
            self.states["HUM_Out"] = hvac.steam_humidify(current_state, total_flow, humidifier_param)
            if not self.states["HUM_Out"]: return False
            current_state = self.states["HUM_Out"]
        elif humidifier_type == "Adiabatic" and humidifier_param > 0:
            self.states["HUM_Out"] = hvac.adiabatic_humidify(current_state, humidifier_param)
            if not self.states["HUM_Out"]: return False
            current_state = self.states["HUM_Out"]
        else:
             self.states["HUM_Out"] = current_state

        # 5. Supply Fan Heat Gain
        if fan_heat_watts > 0:
            self.states["SA"] = hvac.sensible_heat(current_state, fan_heat_watts, total_flow)
            if not self.states["SA"]: return False
        else:
            self.states["SA"] = current_state

        log.info("AHU Heating Cycle calculation completed.")
        return True

    # Add cycles including humidification if needed

    def get_state(self, label: str) -> AirState | None:
        """Gets a calculated state by its label."""
        return self.states.get(label)

    def get_all_states(self) -> list[AirState]:
        """Returns a list of all valid calculated AirState objects in typical process order."""
        # Update order to include humidifier
        order = ["OA", "RA", "MA", "CC_Out", "HC_Out", "HUM_Out", "SA"]
        return [self.states[key] for key in order if self.states.get(key) and self.states[key].is_valid()]

    def get_process_line(self, start_label: str, end_label: str) -> list[AirState] | None:
         """Returns a list containing valid start and end states for plotting a line."""
         start_state = self.get_state(start_label)
         end_state = self.get_state(end_label)
         if start_state and end_state and start_state.is_valid() and end_state.is_valid():
             # Avoid plotting lines between identical states (e.g., bypassed coil)
             if abs(start_state.h - end_state.h) < 10 and abs(start_state.w - end_state.w) < 1e-6: # Tolerance check
                 return None # Don't plot zero-change lines
             return [start_state, end_state]
         return None
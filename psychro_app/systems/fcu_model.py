# psychro_app/systems/fcu_model.py
from psychro_app.core.air_state import AirState
from psychro_app.processes import hvac_processes as hvac
import logging

log = logging.getLogger(__name__)

class FCUModel:
    """Models a simple Fan Coil Unit, typically recirculating room air."""
    def __init__(self, pressure_pa: float):
        self.pressure = pressure_pa
        self.states = {}
        self._reset_states()
        log.info(f"FCUModel initialized at {pressure_pa} Pa.")

    def _reset_states(self):
        """Clears all calculated states."""
        self.states = {
            "Entering": None,   # Typically Room Air / Return Air
            "Coil_Out": None,   # Air leaving coil (either cooling or heating)
            "Supply": None      # Air leaving unit (after fan)
        }
        log.debug("FCU states reset.")

    def set_entering_air(self, tdb: float, rh: float, label: str = "Entering") -> bool:
        """Set the condition of air entering the FCU."""
        self._reset_states() # Clear previous calcs
        log.info(f"Setting FCU inlet: {label}({tdb=:.1f}, {rh=:.2f})")
        entering_state = AirState(pressure_pa=self.pressure, label=label, tdb=tdb, rh=rh)

        if entering_state.is_valid():
            self.states["Entering"] = entering_state
            return True
        else:
            log.error("Failed to create valid FCU entering air state.")
            self._reset_states()
            return False

    def run_cooling_cycle(self, mass_flow: float, cc_adp: float, cc_bf: float, fan_heat_watts: float = 0) -> bool:
        """Simulates FCU cooling."""
        log.info("Running FCU Cooling Cycle simulation...")
        if not self.states.get("Entering"):
            log.error("Entering air condition must be set and valid before running cycle.")
            return False
        if mass_flow <= 1e-9:
             log.error("FCU Mass flow must be positive.")
             return False

        # 1. Cooling Coil (Entering -> Coil_Out)
        self.states["Coil_Out"] = hvac.cooling_coil_simplified(self.states["Entering"], mass_flow, cc_adp, cc_bf)
        if not self.states["Coil_Out"]: return False # Stop if cooling failed

        # 2. Fan Heat (Coil_Out -> Supply)
        if fan_heat_watts > 0:
            self.states["Supply"] = hvac.sensible_heat(self.states["Coil_Out"], fan_heat_watts, mass_flow)
        else:
            self.states["Supply"] = self.states["Coil_Out"] # No fan heat
        if not self.states["Supply"]: return False

        log.info("FCU Cooling Cycle calculation completed.")
        return True

    def run_heating_cycle(self, mass_flow: float, heating_q_sensible: float, fan_heat_watts: float = 0) -> bool:
        """Simulates FCU heating."""
        log.info("Running FCU Heating Cycle simulation...")
        if not self.states.get("Entering"):
            log.error("Entering air condition must be set and valid before running cycle.")
            return False
        if mass_flow <= 1e-9:
             log.error("FCU Mass flow must be positive.")
             return False

        # 1. Heating Coil (Simplified as sensible heat applied to entering air: Entering -> Coil_Out)
        # We label the result 'Coil_Out' for consistency in state tracking.
        if heating_q_sensible > 0:
             heated_state = hvac.sensible_heat(self.states["Entering"], heating_q_sensible, mass_flow)
             self.states["Coil_Out"] = heated_state
        else:
             self.states["Coil_Out"] = self.states["Entering"] # No heating
        if not self.states["Coil_Out"]: return False # Stop if heating failed

        # 2. Fan Heat (Coil_Out -> Supply)
        if fan_heat_watts > 0:
            self.states["Supply"] = hvac.sensible_heat(self.states["Coil_Out"], fan_heat_watts, mass_flow)
        else:
            self.states["Supply"] = self.states["Coil_Out"] # No fan heat
        if not self.states["Supply"]: return False

        log.info("FCU Heating Cycle calculation completed.")
        return True

    def get_state(self, label: str) -> AirState | None:
        """Gets a calculated state by its label."""
        return self.states.get(label)

    def get_all_states(self) -> list[AirState]:
        """Returns a list of all valid calculated AirState objects in typical process order."""
        order = ["Entering", "Coil_Out", "Supply"]
        return [self.states[key] for key in order if self.states.get(key) and self.states[key].is_valid()]

    def get_process_line(self, start_label: str, end_label: str) -> list[AirState] | None:
         """Returns a list containing valid start and end states for plotting a line."""
         start_state = self.get_state(start_label)
         end_state = self.get_state(end_label)
         if start_state and end_state and start_state.is_valid() and end_state.is_valid():
              # Avoid plotting lines between identical states
             if abs(start_state.h - end_state.h) < 10 and abs(start_state.w - end_state.w) < 1e-6:
                 return None
             return [start_state, end_state]
         return None
# psychro_app/processes/hvac_processes.py
from psychro_app.core.air_state import AirState
from psychro_app.core import psychrolib_wrapper as psy_wrap
from psychro_app.utils import constants
import logging

log = logging.getLogger(__name__)

def calculate_cp_moist_air(w: float) -> float:
    """Calculate specific heat of moist air (J/kg.K) based on humidity ratio."""
    if w < 0:
        log.warning(f"Received negative humidity ratio {w} for Cp calculation, using w=0.")
        w = 0
    return constants.CP_AIR_DRY + constants.CP_WATER_VAPOR * w

def mix_air(state1: AirState, mass_flow1: float, state2: AirState, mass_flow2: float) -> AirState | None:
    """
    Mixes two air streams based on mass flow rates.

    Args:
        state1: AirState of the first stream.
        mass_flow1: Mass flow rate of the first stream (kg/s).
        state2: AirState of the second stream.
        mass_flow2: Mass flow rate of the second stream (kg/s).

    Returns:
        A new AirState object representing the mixed condition, or None if inputs are invalid.
    """
    if not state1.is_valid() or not state2.is_valid():
        log.error("Cannot mix invalid air states.")
        return None
    if mass_flow1 < 0 or mass_flow2 < 0:
        log.error(f"Mass flows cannot be negative ({mass_flow1=}, {mass_flow2=}).")
        return None
    if state1.pressure != state2.pressure:
        log.warning(f"Mixing air streams with different pressures ({state1.pressure} Pa vs {state2.pressure} Pa). Using pressure from state1.")
        # Or raise error, depending on requirements

    total_mass_flow = mass_flow1 + mass_flow2
    if total_mass_flow <= 1e-9: # Avoid division by zero or near-zero
        log.warning("Total mass flow for mixing is zero or negligible. Returning state1.")
        # Or handle as an error? Returning one state might be okay if one flow is zero.
        if mass_flow1 > mass_flow2: return state1
        else: return state2


    # Weighted averages based on mass flow for conserved properties (W and h)
    mix_w = (mass_flow1 * state1.w + mass_flow2 * state2.w) / total_mass_flow
    mix_h = (mass_flow1 * state1.h + mass_flow2 * state2.h) / total_mass_flow
    mix_pressure = state1.pressure # Assume constant pressure mixing

    # Create the new state using the calculated h and w
    mix_state = AirState(pressure_pa=mix_pressure, label="Mixed Air")
    success = mix_state.update(h=mix_h, w=mix_w) # Use psychrolib to find Tdb etc.

    if not success:
        log.error(f"Failed to calculate mixed air state properties from h={mix_h}, w={mix_w}")
        return None

    log.info(f"Mixed air: w={mix_w:.5f} kg/kg, h={mix_h:.0f} J/kg -> Tdb={mix_state.tdb:.1f}°C")
    return mix_state


def sensible_heat(state_in: AirState, q_sensible: float, mass_flow: float) -> AirState | None:
    """
    Adds or removes sensible heat only (humidity ratio remains constant).

    Args:
        state_in: The incoming AirState.
        q_sensible: Sensible heat added (positive) or removed (negative) in Watts (J/s).
        mass_flow: Mass flow rate of the air (kg/s).

    Returns:
        A new AirState object after sensible heat exchange, or None if inputs are invalid.
    """
    if not state_in.is_valid():
        log.error("Cannot apply sensible heat to invalid air state.")
        return None
    if mass_flow <= 1e-9:
        log.error("Mass flow must be positive for sensible heat calculation.")
        return None # Or return state_in?

    # Calculate enthalpy change per kg of dry air
    delta_h = q_sensible / mass_flow
    h_out = state_in.h + delta_h
    w_out = state_in.w # Humidity ratio remains constant

    state_out = AirState(pressure_pa=state_in.pressure, label=f"{state_in.label}_SensHeat")
    success = state_out.update(h=h_out, w=w_out) # Calculate resulting state

    if not success:
        log.error(f"Failed to calculate sensible heat state from h={h_out}, w={w_out}")
        return None

    log.info(f"Sensible heat: Q={q_sensible:.0f} W, m={mass_flow:.2f} kg/s -> Tdb change {state_in.tdb:.1f}°C -> {state_out.tdb:.1f}°C")
    return state_out


def cooling_coil_simplified(state_in: AirState, mass_flow: float, adp_temp: float, bypass_factor: float) -> AirState | None:
    """
    Simplified cooling coil model using Apparatus Dew Point (ADP) and Bypass Factor (BF).
    Handles both sensible and latent cooling.

    Args:
        state_in: The incoming AirState.
        mass_flow: Mass flow rate (kg/s). Required if calculating coil load, currently unused here but good practice.
        adp_temp: Apparatus Dew Point temperature (°C). Assumed saturated state on coil.
        bypass_factor: Fraction of air that bypasses the coil effects (0 to 1).

    Returns:
        A new AirState representing the air leaving the coil, or None if inputs invalid.
    """
    if not state_in.is_valid():
        log.error("Cannot model cooling coil for invalid input air state.")
        return None
    if not (0 <= bypass_factor <= 1):
        log.error(f"Bypass factor must be between 0 and 1, got {bypass_factor}.")
        return None
    # ADP must be below incoming Tdb for cooling, could add check?

    # Get properties at ADP (assumed saturated)
    adp_state = AirState(pressure_pa=state_in.pressure, label="ADP_Internal")
    adp_valid = adp_state.update(tdb=adp_temp, rh=1.0) # ADP is saturated

    if not adp_valid:
        log.error(f"Could not calculate valid ADP state for T={adp_temp}°C, RH=100%")
        return None

    # Check if incoming air is already drier/colder than ADP
    # If Tdb_in <= ADP, only sensible cooling occurs towards ADP temp (or no change if Tdb_in == ADP)
    # If W_in <= W_adp, only sensible cooling occurs towards ADP temp
    # More accurately, compare enthalpy: if h_in <= h_adp, little cooling occurs.
    # Let's use the standard mixing formula based on BF:
    # Property_out = Property_adp + BF * (Property_in - Property_adp)
    # This works for Tdb, W, and h. We'll use h and w as they define the state.

    w_out = adp_state.w + bypass_factor * (state_in.w - adp_state.w)
    h_out = adp_state.h + bypass_factor * (state_in.h - adp_state.h)

    state_out = AirState(pressure_pa=state_in.pressure, label=f"{state_in.label}_CoilOut")
    success = state_out.update(h=h_out, w=w_out)

    if not success:
        log.error(f"Failed to calculate cooling coil output state from h={h_out}, w={w_out}")
        return None

    log.info(f"Cooling coil: Tdb_in={state_in.tdb:.1f}, W_in={state_in.w*1000:.2f} -> "
             f"ADP={adp_temp:.1f}, BF={bypass_factor:.2f} -> "
             f"Tdb_out={state_out.tdb:.1f}, W_out={state_out.w*1000:.2f}")

    # Optional: Calculate Coil Load
    # q_total = mass_flow * (state_in.h - state_out.h) # Watts (negative for cooling)
    # q_sensible = mass_flow * calculate_cp_moist_air(state_in.w) * (state_in.tdb - state_out.tdb) # Approx
    # q_latent = q_total - q_sensible
    # log.info(f"Coil Load: Total={q_total:.0f} W, Sensible={q_sensible:.0f} W, Latent={q_latent:.0f} W")

    return state_out

# --- Add other processes as needed (e.g., steam_humidify, adiabatic_humidify) ---
def steam_humidify(state_in: AirState, mass_flow: float, water_mass_flow_added: float) -> AirState | None:
    """
    Adds moisture using steam (adds enthalpy and humidity ratio).

    Args:
        state_in: The incoming AirState.
        mass_flow: Mass flow rate of the air (kg/s).
        water_mass_flow_added: Mass flow rate of steam injected (kg/s).

    Returns:
        A new AirState object after steam humidification, or None if inputs are invalid.
    """
    if not state_in.is_valid():
        log.error("Cannot humidify invalid air state.")
        return None
    if mass_flow <= 1e-9:
        log.error("Air mass flow must be positive for humidification.")
        return None
    if water_mass_flow_added < 0:
        log.warning("Water mass flow added cannot be negative. Assuming 0.")
        water_mass_flow_added = 0
    if water_mass_flow_added == 0:
        return state_in # No change if no water added

    # Calculate added humidity ratio and enthalpy per kg of dry air
    w_added = water_mass_flow_added / mass_flow
    w_out = state_in.w + w_added

    # Calculate enthalpy added by steam
    # Enthalpy added = mass_water * h_steam
    # Specific enthalpy added (per kg dry air) = (mass_water * h_steam) / mass_air
    h_added_per_kg_air = (water_mass_flow_added * constants.H_STEAM_J_KG) / mass_flow
    h_out = state_in.h + h_added_per_kg_air

    state_out = AirState(pressure_pa=state_in.pressure, label=f"{state_in.label}_Humidified")
    success = state_out.update(h=h_out, w=w_out) # Calculate resulting state

    if not success:
        log.error(f"Failed to calculate humidified state from h={h_out}, w={w_out}")
        return None

    log.info(f"Steam humidification: Water={water_mass_flow_added*3600:.2f} kg/h -> "
             f"W change {state_in.w*1000:.2f} -> {state_out.w*1000:.2f} g/kg, "
             f"Tdb change {state_in.tdb:.1f}°C -> {state_out.tdb:.1f}°C")
    return state_out
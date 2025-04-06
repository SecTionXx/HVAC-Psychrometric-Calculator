# psychro_app/utils/constants.py

# --- Physical Constants (SI Units) ---
STANDARD_PRESSURE_PA = 101325.0  # Pa (Standard atmospheric pressure at sea level)
CP_AIR_DRY = 1006.0      # J/(kg*K) Specific heat of dry air (approx, constant)
CP_WATER_VAPOR = 1860.0  # J/(kg*K) Specific heat of water vapor (approx, constant)
H_FG_WATER_0C = 2501000.0 # J/kg Latent heat of vaporization of water at 0°C (approx)

# Enthalpy of steam (saturated steam at 1 atm is ~2676 kJ/kg) - adjust if needed
# Use a reasonable average value if exact steam conditions aren't known.
H_STEAM_J_KG = 2676000.0 # J/kg

# --- Conversion Factors ---
CFM_TO_M3H = 1.69901
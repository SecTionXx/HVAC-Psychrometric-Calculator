# psychro_app/core/psychrolib_wrapper.py
import psychrolib as psy
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Set SI units globally for the psychrolib module
try:
    psy.SetUnitSystem(psy.SI)
    log.info("PsychroLib units set to SI.")
except Exception as e:
    log.error(f"Failed to set PsychroLib units: {e}")

def get_all_properties(pressure_pa: float, **kwargs) -> dict | None:
    """
    Calculates all psychrometric properties given pressure and two other known properties.

    Args:
        pressure_pa: Atmospheric pressure in Pascals.
        **kwargs: Exactly two keyword arguments defining the input pair.
                  Expected keys: 'tdb' (Dry Bulb C), 'rh' (Relative Humidity 0-1),
                                 'twb' (Wet Bulb C), 'w' (Humidity Ratio kg/kg),
                                 'tdp' (Dew Point C), 'h' (Enthalpy J/kg).

    Returns:
        A dictionary containing all properties ('tdb', 'twb', 'rh', 'w', 'h', 'tdp', 'v'),
        or None if calculation fails. Returns properties in SI units. RH is 0-1.
    """
    if len(kwargs) != 2:
        log.error(f"Exactly two input properties required, got: {kwargs.keys()}")
        return None

    inputs = kwargs.keys()
    props = {}
    tdb = kwargs.get('tdb')
    rh = kwargs.get('rh')
    twb = kwargs.get('twb')
    w = kwargs.get('w')
    tdp = kwargs.get('tdp')
    h = kwargs.get('h')

    try:
        # --- Calculate core properties based on input pair ---
        if {'tdb', 'rh'} <= inputs:
            if rh is None or not (0 <= rh <= 1):
                 log.warning(f"RH input out of range (0-1): {rh}. Calculation might fail.")
                 # psychrolib handles internal range checks, but good to warn
            _w = psy.GetHumRatioFromRelHum(tdb, rh, pressure_pa)
            _twb = psy.GetTWetBulbFromRelHum(tdb, rh, pressure_pa) # Corrected capitalization
            _tdp = psy.GetTDewPointFromRelHum(tdb, rh) # Pressure independent approx.
            _h = psy.GetMoistAirEnthalpy(tdb, _w)
            _v = psy.GetMoistAirVolume(tdb, _w, pressure_pa)
            props.update({'tdb': tdb, 'rh': rh, 'w': _w, 'twb': _twb, 'tdp': _tdp, 'h': _h, 'v': _v})

        elif {'tdb', 'w'} <= inputs:
            _rh = psy.GetRelHumFromHumRatio(tdb, w, pressure_pa)
            _twb = psy.GetTWetBulbFromHumRatio(tdb, w, pressure_pa)
            _tdp = psy.GetTDewPointFromHumRatio(tdb, w, pressure_pa)
            _h = psy.GetMoistAirEnthalpy(tdb, w)
            _v = psy.GetMoistAirVolume(tdb, w, pressure_pa)
            props.update({'tdb': tdb, 'w': w, 'rh': _rh, 'twb': _twb, 'tdp': _tdp, 'h': _h, 'v': _v})

        elif {'tdb', 'twb'} <= inputs:
            # Ensure Twb <= Tdb
            if twb > tdb:
                log.warning(f"Input Twb ({twb}°C) > Tdb ({tdb}°C). Setting Twb = Tdb for calculation.")
                twb = tdb
            _w = psy.GetHumRatioFromTWetBulb(tdb, twb, pressure_pa)
            _rh = psy.GetRelHumFromHumRatio(tdb, _w, pressure_pa)
            _tdp = psy.GetTDewPointFromHumRatio(tdb, _w, pressure_pa) # Use w for consistency
            _h = psy.GetMoistAirEnthalpy(tdb, _w)
            _v = psy.GetMoistAirVolume(tdb, _w, pressure_pa)
            props.update({'tdb': tdb, 'twb': twb, 'w': _w, 'rh': _rh, 'tdp': _tdp, 'h': _h, 'v': _v})

        elif {'tdb', 'tdp'} <= inputs:
            # Ensure Tdp <= Tdb
            if tdp > tdb:
                 log.warning(f"Input Tdp ({tdp}°C) > Tdb ({tdb}°C). Setting Tdp = Tdb for calculation.")
                 tdp = tdb
            _w = psy.GetHumRatioFromTDewPoint(tdp, pressure_pa)
            _rh = psy.GetRelHumFromHumRatio(tdb, _w, pressure_pa)
            _twb = psy.GetTWetBulbFromHumRatio(tdb, _w, pressure_pa)
            _h = psy.GetMoistAirEnthalpy(tdb, _w)
            _v = psy.GetMoistAirVolume(tdb, _w, pressure_pa)
            props.update({'tdb': tdb, 'tdp': tdp, 'w': _w, 'rh': _rh, 'twb': _twb, 'h': _h, 'v': _v})

        elif {'h', 'w'} <= inputs:
            # This requires an inverse calculation from psychrolib
            _tdb = psy.GetTDryBulbFromEnthalpyAndHumRatio(h, w)
            _rh = psy.GetRelHumFromHumRatio(_tdb, w, pressure_pa)
            _twb = psy.GetTWetBulbFromHumRatio(_tdb, w, pressure_pa)
            _tdp = psy.GetTDewPointFromHumRatio(_tdb, w, pressure_pa)
            _v = psy.GetMoistAirVolume(_tdb, w, pressure_pa)
            props.update({'h': h, 'w': w, 'tdb': _tdb, 'rh': _rh, 'twb': _twb, 'tdp': _tdp, 'v': _v})

        # Add more input pair handlers (Twb, RH), (Twb, w), (Tdp, RH) etc. if needed

        else:
            log.error(f"Unsupported input property combination: {inputs}")
            return None

        # Ensure all standard keys exist, even if None was calculated (e.g., due to out of range)
        final_props = {
            'tdb': props.get('tdb'),
            'twb': props.get('twb'),
            'rh': props.get('rh'),
            'w': props.get('w'),
            'h': props.get('h'),
            'tdp': props.get('tdp'),
            'v': props.get('v'),
            'pressure_pa': pressure_pa
        }
        return final_props

    except ValueError as ve:
        # Psychrolib often raises ValueError for out-of-range inputs
        log.error(f"Psychrolib calculation error (likely input out of range): {ve} for inputs {kwargs} at P={pressure_pa} Pa")
        return None
    except Exception as e:
        log.error(f"Unexpected psychrolib calculation error: {e} for inputs {kwargs} at P={pressure_pa} Pa", exc_info=True)
        return None

# --- Helper functions (Optional but potentially useful) ---
def get_sat_press(tdb: float) -> float | None:
    """Get saturation pressure (Pa)"""
    try:
        return psy.GetSatVapPres(tdb)
    except ValueError:
        log.warning(f"Temperature {tdb}°C out of range for GetSatVapPres.")
        return None

def get_sat_hum_ratio(tdb: float, pressure_pa: float) -> float | None:
    """Get saturation humidity ratio (kg/kg)"""
    try:
        # Ensure tdb is reasonable, psychrolib might error on very low temps
        if tdb < -100: # Example lower bound check
             log.warning(f"Temperature {tdb}°C potentially too low for GetSatHumRatio.")
             return 0.0 # Return a sensible minimum?
        return psy.GetSatHumRatio(tdb, pressure_pa)
    except ValueError:
        log.warning(f"Temperature {tdb}°C or pressure {pressure_pa} Pa out of range for GetSatHumRatio.")
        return None

def get_tdb_from_h_w(h: float, w: float) -> float | None:
    """Get Dry Bulb Temp from Enthalpy and Humidity Ratio"""
    try:
        return psy.GetTDryBulbFromEnthalpyAndHumRatio(h, w)
    except ValueError:
         log.warning(f"Input h={h} J/kg, w={w} kg/kg out of range for GetTDryBulbFromEnthalpyAndHumRatio.")
         return None
# 📊_Calculator.py
# (Main app file - Indentation Corrected in FCU block)

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import logging
import json # Might be used for Save/Load later

# --- Import backend modules ---
# Ensure Python can find the 'psychro_app' package
try:
    from psychro_app.core.air_state import AirState
    from psychro_app.systems.ahu_model import AHUModel
    from psychro_app.systems.fcu_model import FCUModel
    from psychro_app.utils.plotter import plot_psychro_chart, plot_points, plot_process
    from psychro_app.utils import constants
    from psychro_app.processes import hvac_processes as hvac
except ModuleNotFoundError:
    st.error(
        "Fatal Error: Could not find the 'psychro_app' backend package.\n"
        "Please ensure you are running Streamlit from the main project directory "
        "(`psychro_project`) which contains both this script (`📊_Calculator.py`) "
        "and the `psychro_app` folder."
    )
    st.stop() # Halt execution

# --- Basic Logging Setup ---
log = logging.getLogger(__name__)

# --- Page Configuration ---
st.set_page_config(page_title="Psychrometric Calculator", layout="wide", initial_sidebar_state="expanded")

st.title("📊 HVAC Psychrometric Calculator")
st.markdown("Interactively calculate and visualize HVAC processes.")

# --- ======================= MANUAL CONTENT ======================= ---
MANUAL_TEXT = """
## 📖 User Manual: HVAC Psychrometric Calculator
**Version: 1.2**

---
### 1. Introduction
Welcome! This application allows you to:
*   Calculate air properties using the **Direct Point Calculator**.
*   Simulate **AHU** and **FCU** processes (Mixing, Cooling, Heating, Reheat, Humidification) via the **Sidebar Configuration**.
*   Visualize processes on the **Psychrometric Chart**.
*   Analyze **Coil Loads** and **SHR**.
*   **Download** simulation results (CSV).
---
### 2. Getting Started
*   **Prerequisites:** Python 3.8+, pip.
*   **Installation:** Get code, navigate to root, create/activate venv, `pip install -r requirements.txt`.
*   **Running:** From project root (with venv active): `streamlit run 📊_Calculator.py`
---
### 3. Interface Overview
*   **Sidebar (Left):** Configure simulation (Pressure, System, Mode), enter parameters, calculate.
*   **Main Area:** Contains: Direct Point Calculator, User Manual (this), Results Overview, State Points Table, Download Button, Psychrometric Chart.
---
### 4. Using the Direct Point Calculator
1.  Expand "POINT CALCULATOR".
2.  Enter Pressure (Pa).
3.  Select Input Pair (e.g., "Tdb / RH").
4.  Enter Values (Note units: RH 0-1, W kg/kg, h J/kg).
5.  Click "Calculate Point Properties".
6.  View calculated properties below.
---
### 5. Running an HVAC Simulation
Use the **Sidebar**:
1.  Set Pressure.
2.  Select System & Mode.
3.  Enter Parameters in expanders (`Inlet Air`, `Airflow & Fan`, `Conditioning`).
4.  Click "▶️ Calculate [AHU/FCU] States".
---
### 6. Understanding the Results (Main Area)
*   **Overview Metrics:** Supply Tdb/RH, Coil Load (kW) [+Cooling/-Heating], Coil SHR.
*   **State Points Table:** Properties & Volumetric Flow (m³/h, CFM) at each step.
*   **Download Button:** Get table as CSV.
*   **Psychrometric Chart (Expander):** Visual plot. Markers = States (Legend), Lines = Processes.
---
### 7. Example: AHU Cooling
*(Detailed example steps omitted for brevity - refer to full manual if needed)*
---
### 8. Troubleshooting
*   **`ModuleNotFoundError... psychro_app`:** Running from wrong directory. Run from project root.
*   **Calculation Failed:** Check inputs (units, validity). Check pressure. See terminal for errors.
*   **Chart Issues:** Ensure calculation succeeded.
"""
with st.expander("📖 View User Manual", expanded=False):
    st.markdown(MANUAL_TEXT)

st.divider()

# --- Initialize Session State ---
if 'ahu_model' not in st.session_state: st.session_state.ahu_model = None
if 'fcu_model' not in st.session_state: st.session_state.fcu_model = None
if 'current_pressure_pa' not in st.session_state: st.session_state.current_pressure_pa = constants.STANDARD_PRESSURE_PA
if 'calculated_metrics' not in st.session_state: st.session_state.calculated_metrics = {}
if 'direct_calc_result' not in st.session_state: st.session_state.direct_calc_result = None
if 'last_total_flow' not in st.session_state: st.session_state.last_total_flow = 0

# --- Helper functions ---
def calculate_fan_heat(mass_flow_kg_s, fan_temp_rise_c, air_state):
    if not air_state or not air_state.is_valid() or mass_flow_kg_s <= 0 or fan_temp_rise_c <=0: return 0
    try: cp = hvac.calculate_cp_moist_air(air_state.w); return mass_flow_kg_s * cp * fan_temp_rise_c
    except Exception as e: log.error(f"Error calculating fan heat: {e}"); return 0

def calculate_coil_metrics(state_in: AirState, state_out: AirState, mass_flow: float) -> dict:
    metrics = {'total_load_kw': 0, 'sensible_load_kw': 0, 'latent_load_kw': 0, 'shr': 1.0}
    if not state_in or not state_out or not state_in.is_valid() or not state_out.is_valid() or mass_flow <= 0: return metrics
    try:
        h_in, h_out = state_in.h, state_out.h; w_in = state_in.w; tdb_in, tdb_out = state_in.tdb, state_out.tdb
        q_total_watts = mass_flow * (h_in - h_out); metrics['total_load_kw'] = q_total_watts / 1000.0
        cp_in = hvac.calculate_cp_moist_air(w_in)
        q_sensible_watts = mass_flow * cp_in * (tdb_in - tdb_out); metrics['sensible_load_kw'] = q_sensible_watts / 1000.0
        q_latent_watts = q_total_watts - q_sensible_watts; metrics['latent_load_kw'] = q_latent_watts / 1000.0
        if abs(q_total_watts) > 1e-6: metrics['shr'] = max(0.0, min(q_sensible_watts / q_total_watts, 1.05))
        elif abs(q_sensible_watts) > 1e-6: metrics['shr'] = 1.0
        else: metrics['shr'] = 1.0
    except Exception as e: log.error(f"Error calculating coil metrics: {e}")
    return metrics

# --- Direct State Point Calculator ---
with st.expander("POINT CALCULATOR: Find Air Properties", expanded=False):
    st.markdown("Calculate properties from two known values and pressure.")
    calc_pressure = st.number_input("Pressure (Pa)", min_value=80000, max_value=120000, value=int(st.session_state.current_pressure_pa), step=100, key="calc_pressure")
    input_pair_options = { "Tdb / RH": ('tdb', 'rh'), "Tdb / Twb": ('tdb', 'twb'), "Tdb / W": ('tdb', 'w'), "Tdb / Tdp": ('tdb', 'tdp'), "h / W": ('h', 'w'),}
    selected_pair_label = st.selectbox("Input Pair", options=input_pair_options.keys(), key="calc_input_pair")
    key1, key2 = input_pair_options[selected_pair_label]
    col_calc1, col_calc2 = st.columns(2)
    with col_calc1:
        label1 = f"{key1.upper()}"; unit1 = "°C" if 't' in key1 else ("(0-1)" if key1=='rh' else ("(kg/kg)" if key1=='w' else ("(J/kg)" if key1=='h' else ""))); default1 = 25.0 if 'tdb' in key1 else (0.5 if key1=='rh' else (20.0 if 'twb' in key1 else (15.0 if 'tdp' in key1 else (0.01 if key1=='w' else 50000.0))))
        val1 = st.number_input(f"Value 1: {label1} {unit1}", value=default1, format="%.4f", key="calc_val1")
    with col_calc2:
        label2 = f"{key2.upper()}"; unit2 = "°C" if 't' in key2 else ("(0-1)" if key2=='rh' else ("(kg/kg)" if key2=='w' else ("(J/kg)" if key2=='h' else ""))); default2 = 0.5 if key2=='rh' else (20.0 if 'twb' in key2 else (15.0 if 'tdp' in key2 else (0.01 if key2=='w' else 50000.0)))
        val2 = st.number_input(f"Value 2: {label2} {unit2}", value=default2, format="%.4f", key="calc_val2")
    if st.button("Calculate Point Properties", key="calc_point"):
        inputs = {key1: val1, key2: val2}
        if key1 == 'rh' and not (0 <= val1 <= 1): st.warning("RH (Value 1) should be 0-1."); inputs[key1] = max(0, min(val1, 1))
        if key2 == 'rh' and not (0 <= val2 <= 1): st.warning("RH (Value 2) should be 0-1."); inputs[key2] = max(0, min(val2, 1))
        log.info(f"Direct calculation: P={calc_pressure}, Inputs={inputs}")
        from psychro_app.core import psychrolib_wrapper as psy_wrap
        props_dict = psy_wrap.get_all_properties(calc_pressure, **inputs)
        if props_dict:
             st.session_state.direct_calc_result = {'label': "Calculated Pt", 'pressure_pa': calc_pressure, 'tdb_c': props_dict.get('tdb'), 'twb_c': props_dict.get('twb'), 'rh_frac': props_dict.get('rh'), 'rh_percent': props_dict.get('rh') * 100 if props_dict.get('rh') is not None else None, 'w_kg_kg': props_dict.get('w'), 'w_g_kg': props_dict.get('w') * 1000 if props_dict.get('w') is not None else None, 'h_j_kg': props_dict.get('h'), 'h_kj_kg': props_dict.get('h') / 1000 if props_dict.get('h') is not None else None, 'tdp_c': props_dict.get('tdp'), 'v_m3_kg': props_dict.get('v'), 'is_valid': True }
             st.success("Point calculated!")
        else: st.session_state.direct_calc_result = None; st.error("Failed to calculate point.")
    if st.session_state.direct_calc_result:
        st.write("---"); st.subheader("Calculated Properties:")
        props = st.session_state.direct_calc_result; calc_cols = st.columns(3)
        calc_cols[0].metric("Tdb (°C)", f"{props['tdb_c']:.2f}" if props['tdb_c'] is not None else "N/A"); calc_cols[1].metric("RH (%)", f"{props['rh_percent']:.1f}" if props['rh_percent'] is not None else "N/A"); calc_cols[2].metric("W (g/kg)", f"{props['w_g_kg']:.2f}" if props['w_g_kg'] is not None else "N/A")
        calc_cols[0].metric("Twb (°C)", f"{props['twb_c']:.2f}" if props['twb_c'] is not None else "N/A"); calc_cols[1].metric("Tdp (°C)", f"{props['tdp_c']:.2f}" if props['tdp_c'] is not None else "N/A"); calc_cols[2].metric("h (kJ/kg)", f"{props['h_kj_kg']:.1f}" if props['h_kj_kg'] is not None else "N/A")
        calc_cols[0].metric("V (m³/kg)", f"{props['v_m3_kg']:.4f}" if props['v_m3_kg'] is not None else "N/A")

st.divider()

# --- Sidebar for Main Simulation ---
with st.sidebar:
    st.header("⚙️ Simulation Configuration")
    st.markdown("*(1) Select System & Mode*")
    st.session_state.current_pressure_pa = st.number_input( "Atmospheric Pressure (Pa)", min_value=80000, max_value=120000, value=int(st.session_state.current_pressure_pa), step=100, help=f"Standard: {constants.STANDARD_PRESSURE_PA:.0f} Pa.", key="pressure_input_sidebar")
    pressure_pa = st.session_state.current_pressure_pa
    system_type = st.radio("System Type:", ('AHU', 'FCU'), key="system_type_radio", horizontal=True)
    if system_type == 'AHU': mode = st.radio("AHU Mode:", ('Cooling', 'Heating'), key="ahu_mode_radio", horizontal=True)
    elif system_type == 'FCU': mode = st.radio("FCU Mode:", ('Cooling', 'Heating'), key="fcu_mode_radio", horizontal=True)
    else: mode = None
    st.divider(); st.markdown("*(2) Enter Parameters*")
    if system_type == 'AHU':
        with st.expander("🌀 Inlet Air Conditions", expanded=True):
            oa_col, ra_col = st.columns(2);
            with oa_col: st.markdown("**Outside Air (OA)**"); oa_tdb = st.number_input("Tdb (°C)", -20.0, 55.0, 32.0, 0.5, key="oa_tdb"); oa_rh_perc = st.slider("RH (%)", 0, 100, 60, 1, key="oa_rh"); oa_rh = oa_rh_perc / 100.0
            with ra_col: st.markdown("**Return Air (RA)**"); ra_tdb = st.number_input("Tdb (°C)", 10.0, 40.0, 24.0, 0.5, key="ra_tdb"); ra_rh_perc = st.slider("RH (%)", 0, 100, 50, 1, key="ra_rh"); ra_rh = ra_rh_perc / 100.0
        with st.expander("💨 Airflow & Fan", expanded=True):
            total_ahu_flow = st.number_input("Total Mass Flow (kg/s)", 0.1, 50.0, 2.0, 0.1, key="ahu_flow"); oa_flow_fraction_perc = st.slider("OA Flow Fraction (%)", 0, 100, 20, 1, key="oa_frac"); oa_flow_fraction = oa_flow_fraction_perc / 100.0; fan_temp_rise_c = st.number_input("Fan Temp Rise (°C)", 0.0, 5.0, 0.7, 0.1, key="ahu_fan_rise", help="Sensible heat gain from fan motor.")
        with st.expander("❄️🔥💧 Conditioning", expanded=True):
            reheat_q_input = 0.0; humidifier_kg_s_input = 0.0; heating_q = 0
            if mode == 'Cooling': st.markdown("**Cooling Coil**"); cc_adp = st.number_input("Coil ADP (°C)", 0.0, 20.0, 10.0, 0.5, key="ahu_cc_adp"); cc_bf = st.slider("Bypass Factor", 0.0, 1.0, 0.1, 0.01, key="ahu_cc_bf"); st.markdown("**Reheat Coil (Optional)**"); reheat_q_input = st.number_input("Sensible Heat Added (W)", 0, 50000, 0, 100, key="ahu_reheat_q")
            elif mode == 'Heating': st.markdown("**Heating Coil**"); heating_q = st.number_input("Sensible Heat Added (W)", 0, 100000, 15000, 100, key="ahu_hc_q")
            st.markdown("**Steam Humidifier (Optional)**"); humidifier_enabled = st.checkbox("Enable Humidifier", key="ahu_hum_enable", value=False);
            if humidifier_enabled: humidifier_kg_h = st.number_input("Water Added (kg/h)", 0.0, 100.0, 5.0, 0.1, key="ahu_hum_kg_h"); humidifier_kg_s_input = humidifier_kg_h / 3600.0
        st.divider(); st.markdown("*(3) Calculate*")
        if st.button("▶️ Calculate AHU States", key="calc_ahu", use_container_width=True):
            st.session_state.fcu_model = None; st.session_state.calculated_metrics = {}; st.session_state.direct_calc_result = None; st.session_state.last_total_flow = 0
            ahu = AHUModel(pressure_pa=pressure_pa); inlet_ok = ahu.set_inlet_conditions(oa_tdb=oa_tdb, oa_rh=oa_rh, ra_tdb=ra_tdb, ra_rh=ra_rh)
            if inlet_ok:
                oa_mass_flow = total_ahu_flow * oa_flow_fraction; ra_mass_flow = total_ahu_flow * (1.0 - oa_flow_fraction); success = False
                with st.spinner("Calculating AHU cycle..."):
                    try:
                        if mode == 'Cooling':
                            success = ahu.run_cooling_cycle( oa_mass_flow, ra_mass_flow, cc_adp, cc_bf, reheat_q_watts=reheat_q_input, humidifier_water_kg_s=humidifier_kg_s_input, fan_heat_watts=0)
                            if success:
                                fan_heat_input_state = ahu.get_state("HUM_Out")
                                if fan_temp_rise_c > 0 and fan_heat_input_state:
                                    fan_q_watts = calculate_fan_heat(total_ahu_flow, fan_temp_rise_c, fan_heat_input_state)
                                    sa_state = hvac.sensible_heat(fan_heat_input_state, fan_q_watts, total_ahu_flow)
                                    if sa_state: ahu.states["SA"] = sa_state
                                    else: success = False # Mark as failed if fan heat fails
                                if success: cc_in = ahu.get_state("MA"); cc_out = ahu.get_state("CC_Out"); st.session_state.calculated_metrics = calculate_coil_metrics(cc_in, cc_out, total_ahu_flow)
                        elif mode == 'Heating':
                            success = ahu.run_heating_cycle( oa_mass_flow, ra_mass_flow, heating_q, humidifier_water_kg_s=humidifier_kg_s_input, fan_heat_watts=0 )
                            if success:
                                fan_heat_input_state = ahu.get_state("HUM_Out")
                                if fan_temp_rise_c > 0 and fan_heat_input_state:
                                     fan_q_watts = calculate_fan_heat(total_ahu_flow, fan_temp_rise_c, fan_heat_input_state)
                                     sa_state = hvac.sensible_heat(fan_heat_input_state, fan_q_watts, total_ahu_flow)
                                     if sa_state: ahu.states["SA"] = sa_state
                                     else: success = False
                        if success and ahu.get_all_states(): st.session_state.ahu_model = ahu; st.session_state.last_total_flow = total_ahu_flow; st.success(f"AHU {mode} cycle calculated!", icon="✅")
                        else: st.session_state.ahu_model = None; st.session_state.last_total_flow = 0; st.error("AHU calculation failed. Check inputs/steps.", icon="❌")
                    except Exception as e: st.session_state.ahu_model = None; st.error(f"Calc error: {e}", icon="🔥"); log.error(f"Streamlit AHU Calc Error:", exc_info=True)
            else: st.error("Failed to set inlet conditions.", icon="⚠️") # This else aligns with 'if inlet_ok:'

    elif system_type == 'FCU':
        with st.expander("🌀 Inlet Air Condition", expanded=True): st.markdown("**Entering Air (e.g., Room Air)**"); room_tdb = st.number_input("Tdb (°C)", 10.0, 40.0, 25.0, 0.5, key="fcu_tdb"); room_rh_perc = st.slider("Entering RH (%)", 0, 100, 55, 1, key="fcu_rh"); room_rh = room_rh_perc / 100.0
        with st.expander("💨 Airflow & Fan", expanded=True): fcu_flow = st.number_input("Mass Flow (kg/s)", 0.05, 5.0, 0.5, 0.05, key="fcu_flow"); fan_temp_rise_c = st.number_input("Fan Temp Rise (°C)", 0.0, 3.0, 0.3, 0.05, key="fcu_fan_rise")
        with st.expander("❄️🔥 Coil Parameters", expanded=True): heating_q = 0
        if mode == 'Cooling': st.markdown("**Cooling Coil**"); cc_adp = st.number_input("Coil ADP (°C)", 0.0, 20.0, 12.0, 0.5, key="fcu_cc_adp"); cc_bf = st.slider("Bypass Factor", 0.0, 1.0, 0.15, 0.01, key="fcu_cc_bf")
        elif mode == 'Heating': st.markdown("**Heating Coil**"); heating_q = st.number_input("Sensible Heat Added (W)", 0, 20000, 3000, 100, key="fcu_hc_q")
        st.divider(); st.markdown("*(3) Calculate*")
        if st.button("▶️ Calculate FCU States", key="calc_fcu", use_container_width=True):
            st.session_state.ahu_model = None; st.session_state.calculated_metrics = {}; st.session_state.direct_calc_result = None; st.session_state.last_total_flow = 0
            fcu = FCUModel(pressure_pa=pressure_pa); inlet_ok = fcu.set_entering_air(tdb=room_tdb, rh=room_rh, label="Entering")

            # --- CORRECTED INDENTATION FOR THIS BLOCK ---
            if inlet_ok: # <--- Outer condition check
                success = False
                with st.spinner("Calculating FCU cycle..."):
                    try: # <--- Inner try block starts here
                        if mode == 'Cooling':
                            success = fcu.run_cooling_cycle(fcu_flow, cc_adp, cc_bf, 0)
                            if success:
                                fan_heat_input_state = fcu.get_state("Coil_Out")
                                if fan_temp_rise_c > 0 and fan_heat_input_state:
                                    fan_q_watts = calculate_fan_heat(fcu_flow, fan_temp_rise_c, fan_heat_input_state)
                                    sa_state = hvac.sensible_heat(fan_heat_input_state, fan_q_watts, fcu_flow)
                                    if sa_state:
                                        fcu.states["Supply"] = sa_state
                                    else:
                                        success = False
                                if success:
                                     cc_in = fcu.get_state("Entering"); cc_out = fcu.get_state("Coil_Out")
                                     st.session_state.calculated_metrics = calculate_coil_metrics(cc_in, cc_out, fcu_flow)
                        elif mode == 'Heating':
                            success = fcu.run_heating_cycle(fcu_flow, heating_q, 0)
                            if success:
                                fan_heat_input_state = fcu.get_state("Coil_Out")
                                if fan_temp_rise_c > 0 and fan_heat_input_state:
                                     fan_q_watts = calculate_fan_heat(fcu_flow, fan_temp_rise_c, fan_heat_input_state)
                                     sa_state = hvac.sensible_heat(fan_heat_input_state, fan_q_watts, fcu_flow)
                                     if sa_state:
                                         fcu.states["Supply"] = sa_state
                                     else:
                                         success = False
                        # Check final success state inside try
                        if success and fcu.get_all_states():
                            st.session_state.fcu_model = fcu
                            st.session_state.last_total_flow = fcu_flow
                            st.success(f"FCU {mode} cycle calculated!", icon="✅")
                        else:
                            st.session_state.fcu_model = None
                            st.session_state.last_total_flow = 0
                            st.error("FCU calculation failed.", icon="❌")

                    except Exception as e: # <--- except aligns with try
                        st.session_state.fcu_model = None
                        st.error(f"Calculation error: {e}", icon="🔥")
                        log.error(f"Streamlit FCU Calc Error:", exc_info=True)

            else: # <--- THIS else ALIGNS WITH 'if inlet_ok:'
                st.error("Failed to set entering air condition.", icon="⚠️")
            # --- END CORRECTED INDENTATION ---

    # --- Common Sidebar Footer ---
    st.sidebar.markdown("---"); st.sidebar.caption("Psychro App v1.2")


# --- ============== Main Display Area ============== ---
st.header("✅ Results Overview")
model_to_display = None; model_name = "System"; total_flow_kg_s = st.session_state.get('last_total_flow', 0)
if system_type == 'AHU' and st.session_state.ahu_model: model_to_display = st.session_state.ahu_model; model_name = "AHU"
elif system_type == 'FCU' and st.session_state.fcu_model: model_to_display = st.session_state.fcu_model; model_name = "FCU"

if not model_to_display: st.info("⬅️ Configure simulation in sidebar & click 'Calculate'. Use Point Calculator above for single states.")
else:
    # --- Display Key Metrics ---
    metrics = st.session_state.calculated_metrics; supply_state_label = "SA" if model_name == "AHU" else "Supply"; supply_state = model_to_display.get_state(supply_state_label)
    col1, col2, col3, col4 = st.columns(4)
    with col1: val = f"{supply_state.tdb:.1f} °C" if supply_state and supply_state.is_valid() else "N/A"; st.metric("Supply Tdb", val)
    with col2: val = f"{supply_state.rh*100:.1f} %" if supply_state and supply_state.is_valid() else "N/A"; st.metric("Supply RH", val)
    with col3: val = "N/A"; help_txt = ""
    if metrics and metrics.get('total_load_kw') is not None: load = metrics['total_load_kw']; val = f"{load:+.2f} kW"; help_txt = f"Cooling load > 0 ({load:.2f} kW rem)" if load > 0 else f"Heating load < 0 ({-load:.2f} kW add)"; st.metric("Coil Load (Total)", val, help=help_txt)
    else: st.metric("Coil Load (Total)", val)
    with col4: val = "N/A"
    if metrics and metrics.get('shr') is not None: val = f"{metrics['shr']:.3f}"; st.metric("Coil SHR", val, help="Sensible Heat Ratio (Qs / Qt)")
    else: st.metric("Coil SHR", val)
    st.divider()
    # --- Display State Points Table ---
    st.subheader(f"💧 {model_name} State Points"); all_states = model_to_display.get_all_states()
    if all_states:
        data_for_table = []; display_columns = ["Label", "Tdb (°C)", "RH (%)", "W (g/kg)", "h (kJ/kg)", "Vol Flow (m³/h)", "Vol Flow (CFM)", "Twb (°C)", "Tdp (°C)", "V (m³/kg)"]
        for state in all_states:
             vol_flow_m3s = total_flow_kg_s * state.v if state.v and total_flow_kg_s > 0 else 0; vol_flow_m3h = vol_flow_m3s * 3600; vol_flow_cfm = vol_flow_m3h / constants.CFM_TO_M3H
             data_for_table.append({ "Label": state.label, "Tdb (°C)": state.get_display_value('tdb_c', 1), "RH (%)": state.get_display_value('rh_percent', 1), "W (g/kg)": state.get_display_value('w_g_kg', 2), "h (kJ/kg)": state.get_display_value('h_kj_kg', 1), "Vol Flow (m³/h)": f"{vol_flow_m3h:.0f}" if state.v else "N/A", "Vol Flow (CFM)": f"{vol_flow_cfm:.0f}" if state.v else "N/A", "Twb (°C)": state.get_display_value('twb_c', 1), "Tdp (°C)": state.get_display_value('tdp_c', 1), "V (m³/kg)": state.get_display_value('v_m3_kg', 4), })
        df = pd.DataFrame(data_for_table, columns=display_columns); st.dataframe(df, hide_index=True, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8'); st.download_button( label="📥 Download Results as CSV", data=csv, file_name=f'{model_name}_{mode}_psychro_results.csv', mime='text/csv', key='download_csv')
        st.divider()
        # --- Display Psychrometric Chart ---
        with st.expander("📈 View Psychrometric Chart", expanded=True):
            try:
                fig, ax = plot_psychro_chart(pressure_pa); plot_points(ax, all_states)
                color_mixing = '#FFA500'; color_cooling = 'blue'; color_heating = 'red'; color_reheat = '#FF00FF'; color_humid = '#00CED1'; color_fan = '#8B0000'
                if isinstance(model_to_display, AHUModel):
                    plot_process(ax, model_to_display.get_process_line("OA", "MA"), color=color_mixing, style='--'); plot_process(ax, model_to_display.get_process_line("RA", "MA"), color=color_mixing, style='--'); plot_process(ax, model_to_display.get_process_line("MA", "CC_Out"), color=color_cooling); plot_process(ax, model_to_display.get_process_line("CC_Out", "HC_Out"), color=color_reheat); plot_process(ax, model_to_display.get_process_line("MA", "HC_Out"), color=color_heating); plot_process(ax, model_to_display.get_process_line("HC_Out", "HUM_Out"), color=color_humid); state_before_fan = model_to_display.get_state("HUM_Out") or model_to_display.get_state("HC_Out"); final_supply_state = model_to_display.get_state("SA");
                    if state_before_fan and final_supply_state: plot_process(ax, [state_before_fan, final_supply_state], color=color_fan)
                elif isinstance(model_to_display, FCUModel):
                     coil_line = model_to_display.get_process_line("Entering", "Coil_Out");
                     if coil_line: line_color = color_cooling if coil_line[1].tdb < coil_line[0].tdb else color_heating; plot_process(ax, coil_line, color=line_color)
                     state_before_fan_fcu = model_to_display.get_state("Coil_Out"); final_supply_state_fcu = model_to_display.get_state("Supply");
                     if state_before_fan_fcu and final_supply_state_fcu: plot_process(ax, [state_before_fan_fcu, final_supply_state_fcu], color=color_fan)
                ax.legend(title="State Points", fontsize='small', loc='upper left', bbox_to_anchor=(1.01, 1.02)); st.pyplot(fig, clear_figure=True)
            except Exception as e: st.error(f"Could not generate psychrometric chart: {e}"); log.error(f"Streamlit Plotting Error:", exc_info=True)
    else: st.warning(f"No valid state points calculated for {model_name}.")
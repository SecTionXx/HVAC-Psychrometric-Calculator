# psychro_app/utils/plotter.py (Revised for Readability)
import matplotlib.pyplot as plt
import numpy as np
from psychro_app.core import psychrolib_wrapper as psy_wrap
from psychro_app.core.air_state import AirState 
from psychro_app.utils import constants
from psychro_app.processes import hvac_processes as hvac
import logging

log = logging.getLogger(__name__)

DEFAULT_TDB_RANGE = (0, 50)
DEFAULT_W_RANGE = (0, 0.030)

def plot_psychro_chart(pressure_pa: float,
                        tdb_range: tuple = DEFAULT_TDB_RANGE,
                        w_range: tuple = DEFAULT_W_RANGE) -> tuple[plt.Figure, plt.Axes]:
    """Creates the background psychrometric chart using Matplotlib.
    
    Key formulas used:
    1. Saturation humidity ratio (W_s):
        - W_s = 0.622 * (Pws / (P - Pws))
        where: Pws = saturation vapor pressure, P = atmospheric pressure
    
    2. Relative humidity lines:
        - W = (RH * W_s)
        where: RH = target relative humidity (0.1 to 1.0)
    
    3. Enthalpy lines (h):
        - h = 1.006 * t + W * (2501 + 1.86 * t)
        where: t = dry bulb temp, W = humidity ratio
    """
    if not (1000 <= pressure_pa <= 120000):  # Valid pressure range check
        raise ValueError(f"Pressure {pressure_pa} Pa is outside valid range")
    
    # Validate temperature and humidity ratio ranges
    if not (-100 <= tdb_range[0] < tdb_range[1] <= 100):
        raise ValueError("Invalid temperature range")
    if not (0 <= w_range[0] < w_range[1] <= 0.1):
        raise ValueError("Invalid humidity ratio range")

    log.info(f"Generating psychrometric chart at {pressure_pa} Pa")
    fig, ax = plt.subplots(figsize=(11, 8)) # Slightly adjusted size

    # --- Background Lines ---
    # Saturation line (100% RH) - Keep prominent
    temps_sat = np.linspace(tdb_range[0], tdb_range[1], 100)
    w_sat = []
    valid_temps_sat = []
    # Enhanced saturation line validation
    for t in temps_sat:
        try:
            w = psy_wrap.get_sat_hum_ratio(t, pressure_pa)
            if w is not None and w_range[0] <= w <= w_range[1] * 1.05: # Extend slightly beyond top range
                # Prevent plotting wildly high W if pressure is low / temp high
                if len(w_sat) > 0 and w > w_sat[-1] * 3:
                    log.warning(f"Suspicious jump in saturation line at T={t}°C")
                    continue # Basic sanity check
                w_sat.append(w)
                valid_temps_sat.append(t)
        except Exception as e:
            log.error(f"Error calculating saturation point at {t}°C: {e}")
    if valid_temps_sat:
        ax.plot(valid_temps_sat, w_sat, color='black', linewidth=1.5, label='Saturation (100% RH)') # Add label
    else:
        log.warning("Could not plot saturation line.")

    # Constant Relative Humidity lines - Standard blue, maybe slightly thinner
    for rh_target in np.arange(0.1, 1.0, 0.1):
        w_rh = []
        temps_rh = []
        for t in temps_sat:
            try:
                _w = psy_wrap.psy.GetHumRatioFromRelHum(t, rh_target, pressure_pa)
                if w_range[0] * 0.95 <= _w <= w_range[1] * 1.05: # Allow slightly outside bounds for continuity
                    w_rh.append(_w)
                    temps_rh.append(t)
            except ValueError: pass
            except Exception as e: log.error(f"Error RH line: {e}"); pass
        if temps_rh:
            ax.plot(temps_rh, w_rh, color='blue', linestyle='-', linewidth=0.6, alpha=0.7) # Thinner, slightly transparent
            # Add RH labels (Improved placement attempt)
            try:
                 # Try placing near right edge, vertically centered on the line within bounds
                target_x_factor = 0.85 # Place label towards 85% of x-range
                idx = min(range(len(temps_rh)), key=lambda i: abs(temps_rh[i] - (tdb_range[0] + (tdb_range[1]-tdb_range[0])*target_x_factor)))

                label_x = temps_rh[idx]
                label_y = w_rh[idx]
                if label_x < tdb_range[1] and label_y < w_range[1]*0.98 and label_y > w_range[0]: # Check bounds
                      ax.text(label_x, label_y, f'{rh_target*100:.0f}%', rotation=30,
                              ha='left', va='bottom', color='blue', fontsize=7, alpha=0.8,
                              bbox=dict(boxstyle='round,pad=0.1', fc='white', alpha=0.6, ec='none')) # Semi-transparent background
            except (IndexError, ValueError): pass

    # Constant Enthalpy lines - Lighter green, dashed, fainter
    h_bl = psy_wrap.psy.GetMoistAirEnthalpy(tdb_range[0], w_range[0])
    h_tr = psy_wrap.psy.GetMoistAirEnthalpy(tdb_range[1], w_range[1])
    h_start = min(h_bl, h_tr, 10000) # Ensure reasonable start
    h_end = max(h_bl, h_tr, 90000) # Ensure reasonable end

    # Adjust number of lines based on range? For now, fixed number.
    num_h_lines = 7
    for h_target in np.linspace(h_start, h_end, num_h_lines):
        if h_target < -50000 or h_target > 200000:  # Reasonable enthalpy bounds
            log.warning(f"Skipping enthalpy line {h_target} J/kg - outside reasonable range")
            continue
         temps_h = []
         ws_h = []
         for t in np.linspace(tdb_range[0], tdb_range[1], 50):
             try:
                 _w = psy_wrap.psy.GetHumRatioFromEnthalpyAndTDryBulb(h_target, t)
                 # Check if within plot bounds, slightly extended
                 if w_range[0] * 0.95 <= _w <= w_range[1] * 1.05:
                    temps_h.append(t)
                    ws_h.append(_w)
             except ValueError: pass
             except Exception as e: log.error(f"Error h line: {e}"); pass
         if temps_h:
             ax.plot(temps_h, ws_h, color='green', linestyle='--', linewidth=0.6, alpha=0.6) # Dashed, thinner, fainter
             # Add enthalpy labels (Improved placement attempt)
             try:
                  # Try placing near top edge, horizontally centered on line within bounds
                idx = min(range(len(ws_h)), key=lambda i: abs(ws_h[i] - w_range[1]*0.9)) # Find point near top
                label_x = temps_h[idx]
                label_y = ws_h[idx]
                if tdb_range[0]*1.02 < label_x < tdb_range[1]*0.98 and label_y < w_range[1]: # Check bounds
                      ax.text(label_x, label_y, f'{h_target/1000:.0f} kJ/kg', rotation=-30,
                              ha='center', va='bottom', color='green', fontsize=7, alpha=0.7,
                              bbox=dict(boxstyle='round,pad=0.1', fc='white', alpha=0.6, ec='none'))
             except (IndexError, ValueError): pass


    # Axes and Labels
    ax.set_xlabel("Dry Bulb Temperature (°C)", fontsize=10)
    ax.set_ylabel("Humidity Ratio (kg water / kg dry air)", fontsize=10)
    ax.set_title(f"Psychrometric Chart at {pressure_pa/1000:.1f} kPa", fontsize=12, weight='bold')
    ax.set_xlim(tdb_range)
    ax.set_ylim(w_range)

    # Set y-axis labels in g/kg for readability
    yticks_kg = np.linspace(w_range[0], w_range[1], 11)
    ax.set_yticks(yticks_kg)
    ax.set_yticklabels([f"{w*1000:.1f}" for w in yticks_kg], fontsize=8)

    # Secondary y-axis label
    ax_secondary_y = ax.secondary_yaxis('right')
    ax_secondary_y.set_ylabel("Humidity Ratio (g water / kg dry air)", fontsize=10)
    ax_secondary_y.set_yticks([]) # Hide ticks on secondary axis


    ax.grid(True, which='major', linestyle=':', linewidth=0.5, alpha=0.6) # Fainter grid
    fig.tight_layout(rect=[0, 0, 0.9, 1]) # Adjust layout to make space for legend if outside

    return fig, ax

def plot_points(ax: plt.Axes, air_states: list):
    """Plots AirState points on the chart and adds them to the legend.
    
    Each point represents a thermodynamic state with properties:
    - tdb: Dry bulb temperature (°C)
    - w: Humidity ratio (kg/kg)
    - Additional properties from AirState (RH, h, etc.)
    """
    if not hasattr(ax, 'plot'): return

    point_marker_size = 7
    label_fontsize = 8
    # Define specific markers/colors for key points
    point_styles = {
        "OA": {"marker": "o", "color": "blue", "ms": point_marker_size + 1},
        "RA": {"marker": "o", "color": "orange", "ms": point_marker_size},
        "MA": {"marker": "o", "color": "green", "ms": point_marker_size},
        "CC_Out": {"marker": "o", "color": "purple", "ms": point_marker_size},
        "HC_Out": {"marker": "o", "color": "red", "ms": point_marker_size},
        "SA": {"marker": "s", "color": "black", "ms": point_marker_size + 1}, # Square for Supply Air
        "Entering": {"marker": "o", "color": "orange", "ms": point_marker_size}, # FCU Entering
        "Coil_Out": {"marker": "o", "color": "purple", "ms": point_marker_size}, # FCU Coil Out
        "Supply": {"marker": "s", "color": "black", "ms": point_marker_size + 1} # FCU Supply
    }
    default_style = {"marker": "o", "color": "grey", "ms": point_marker_size}

    plotted_labels = []
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x_offset = (xlim[1] - xlim[0]) * 0.015 # Offset based on axis width
    y_offset = (ylim[1] - ylim[0]) * 0.015 # Offset based on axis height

    for state in air_states:
        if state and state.is_valid() and state.tdb is not None and state.w is not None:
            style = point_styles.get(state.label, default_style)
            # Plot point - IMPORTANT: Add label here for the legend
            ax.plot(state.tdb, state.w,
                    marker=style["marker"],
                    markersize=style["ms"],
                    color=style["color"],
                    linestyle='None', # No line connecting points here
                    label=state.label, # This adds the point to the legend
                    zorder=10) # High zorder to be on top

            # Add text label near the point
            ax.text(state.tdb + x_offset, state.w + y_offset, state.label,
                    fontsize=label_fontsize, va='bottom', ha='left', zorder=11,
                    bbox=dict(boxstyle='round,pad=0.1', fc='white', alpha=0.6, ec='none')) # Background for label
            plotted_labels.append(state.label)
    log.info(f"Plotted points for legend: {plotted_labels}")


def plot_process(ax: plt.Axes, process_states: list | None, color='grey', style='-', linewidth=1.5):
    """
    Plots a process line connecting AirStates WITHOUT adding to legend.
    
    Process lines represent thermodynamic processes with these key formulas:
    1. Sensible Heat (constant W):
        Q = m * cp * (T2 - T1)
        where: cp = 1006 + 1860*W [J/kg-K]
    
    2. Total Heat:
        Q = m * (h2 - h1)
        where: h = 1006*T + W*(2501000 + 1860*T) [J/kg]
    
    3. Latent Heat (constant T):
        Q = m * hfg * (W2 - W1)
        where: hfg ≈ 2501000 [J/kg]
    
    4. Sensible Heat Ratio (SHR):
        SHR = Qsensible / Qtotal
    
    Args:
        ax: The matplotlib Axes object.
        process_states: List containing two AirState objects [start, end].
        color: Color of the line.
        style: Linestyle (e.g., '-', '--', ':'). Arrow added separately.
        linewidth: Width of the line.
    """
    if not hasattr(ax, 'plot'): return
    if not process_states or len(process_states) < 2:
        log.debug("Not enough states to plot a process line.")
        return

    start_state, end_state = process_states[0], process_states[1]

    # Enhanced validation with process type identification
    if (start_state and end_state and start_state.is_valid() and end_state.is_valid()):
        delta_t = abs(start_state.tdb - end_state.tdb)
        delta_w = abs(start_state.w - end_state.w)
        
        # Skip if changes are too small to plot meaningfully
        if delta_t <= 0.01 and delta_w <= 1e-7:
            log.debug(f"Changes too small to plot: ΔT={delta_t:.3f}°C, ΔW={delta_w*1000:.3f}g/kg")
            return
            
        # Identify process type for logging
        process_type = "Unknown"
        if delta_w < 1e-7:  # Constant humidity ratio
            process_type = "Sensible Only"
        elif delta_t < 0.01:  # Constant temperature
            process_type = "Latent Only"
        else:
            # Calculate SHR if possible
            try:
                delta_h = end_state.h - start_state.h
                cp_avg = 1006 + 1860 * ((start_state.w + end_state.w) / 2)
                q_sensible = cp_avg * delta_t
                shr = abs(q_sensible / delta_h) if abs(delta_h) > 0 else 1.0
                process_type = f"Combined (SHR≈{shr:.2f})"
            except Exception as e:
                log.warning(f"Could not calculate SHR: {e}")

        tdbs = [start_state.tdb, end_state.tdb]
        ws = [start_state.w, end_state.w]
        label_desc = f"{start_state.label} -> {end_state.label} ({process_type})"

        # Plot line WITHOUT label for legend
        ax.plot(tdbs, ws, color=color, linestyle=style, linewidth=linewidth,
                marker='', zorder=5)

        # Add arrow using annotate
        try:
            ax.annotate('', xy=(tdbs[1], ws[1]), xytext=(tdbs[0], ws[0]),
                        arrowprops=dict(arrowstyle="->", color=color, lw=linewidth*0.8),
                        va='center', ha='center', zorder=6)
            log.info(f"Plotted process line: {label_desc}")
        except Exception as e:
            log.error(f"Failed to draw arrow for process {label_desc}: {e}")
    else:
        log.debug(f"Invalid states for process line from {start_state.label if start_state else 'N/A'} to {end_state.label if end_state else 'N/A'}")

def plot_shr_line(ax: plt.Axes, start_state: AirState, shr: float, color='magenta', linestyle=':'):
    """
    Plots the Sensible Heat Ratio (SHR) line originating from a start state.
    
    Args:
        ax: The matplotlib Axes object.
        start_state: The AirState object where the cooling process begins (e.g., MA).
        shr (float): The Sensible Heat Ratio (typically 0 to 1).
        color (str): Line color.
        linestyle (str): Line style.
    """
    if not start_state or not start_state.is_valid() or not (0 <= shr <= 1.1):
        log.warning(f"Cannot plot SHR line from invalid state or invalid SHR ({shr=}).")
        return

    try:
        cp = hvac.calculate_cp_moist_air(start_state.w)
        h_fg = constants.H_FG_WATER_0C

        if abs(shr) < 1e-6:  # Pure latent cooling
            slope_dw_dt = float('inf')
        elif abs(1 - shr) < 1e-6:  # Pure sensible cooling
            slope_dw_dt = 0.0
        else:
            slope_dw_dt = (cp * (1.0 - shr)) / (h_fg * shr)
    except (ZeroDivisionError, TypeError):
        log.error(f"Could not calculate SHR slope for SHR={shr}")
        return

    # Get plot boundaries
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    tdb_start = start_state.tdb
    w_start = start_state.w

    # Calculate intersections with plot boundaries
    points = []
    if slope_dw_dt != float('inf'):
        # Calculate horizontal intersections
        w_at_xmin = w_start + slope_dw_dt * (xlim[0] - tdb_start)
        w_at_xmax = w_start + slope_dw_dt * (xlim[1] - tdb_start)
        if ylim[0] <= w_at_xmin <= ylim[1]: points.append((xlim[0], w_at_xmin))
        if ylim[0] <= w_at_xmax <= ylim[1]: points.append((xlim[1], w_at_xmax))

    if abs(slope_dw_dt) > 1e-9:
        # Calculate vertical intersections
        t_at_ymin = tdb_start + (ylim[0] - w_start) / slope_dw_dt
        t_at_ymax = tdb_start + (ylim[1] - w_start) / slope_dw_dt
        if xlim[0] <= t_at_ymin <= xlim[1]: points.append((t_at_ymin, ylim[0]))
        if xlim[0] <= t_at_ymax <= xlim[1]: points.append((t_at_ymax, ylim[1]))

    if len(points) >= 2:
        points.sort()  # Sort by temperature
        final_points = [points[0], points[-1]]
        line_tdbs = [p[0] for p in final_points]
        line_ws = [p[1] for p in final_points]

        ax.plot(line_tdbs, line_ws, color=color, linestyle=linestyle, linewidth=1.0,
                label=f"SHR Line ({shr:.2f})", zorder=4)
        log.info(f"Plotted SHR line (SHR={shr:.3f}) from Tdb={tdb_start:.1f}, W={w_start:.5f}")
    else:
        log.warning(f"Could not determine valid boundary points for SHR line (SHR={shr:.3f}).")
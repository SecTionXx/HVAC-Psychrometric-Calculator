# psychro_app/utils/plotter.py (Revised for Readability)
import matplotlib.pyplot as plt
import numpy as np
from psychro_app.core import psychrolib_wrapper as psy_wrap
import logging

log = logging.getLogger(__name__)

DEFAULT_TDB_RANGE = (0, 50)
DEFAULT_W_RANGE = (0, 0.030)

def plot_psychro_chart(pressure_pa: float,
                        tdb_range: tuple = DEFAULT_TDB_RANGE,
                        w_range: tuple = DEFAULT_W_RANGE) -> tuple[plt.Figure, plt.Axes]:
    """Creates the background psychrometric chart using Matplotlib."""
    log.info(f"Generating psychrometric chart at {pressure_pa} Pa")
    fig, ax = plt.subplots(figsize=(11, 8)) # Slightly adjusted size

    # --- Background Lines ---
    # Saturation line (100% RH) - Keep prominent
    temps_sat = np.linspace(tdb_range[0], tdb_range[1], 100)
    w_sat = []
    valid_temps_sat = []
    for t in temps_sat:
        w = psy_wrap.get_sat_hum_ratio(t, pressure_pa)
        if w is not None and w_range[0] <= w <= w_range[1] * 1.05: # Extend slightly beyond top range
            # Prevent plotting wildly high W if pressure is low / temp high
            if len(w_sat) > 0 and w > w_sat[-1] * 3: continue # Basic sanity check
            w_sat.append(w)
            valid_temps_sat.append(t)
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
    """Plots AirState points on the chart and adds them to the legend."""
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

    # Check if states are valid and different enough to plot
    if (start_state and end_state and start_state.is_valid() and end_state.is_valid() and
        (abs(start_state.tdb - end_state.tdb) > 0.01 or abs(start_state.w - end_state.w) > 1e-7)):

        tdbs = [start_state.tdb, end_state.tdb]
        ws = [start_state.w, end_state.w]
        label_desc = f"{start_state.label} -> {end_state.label}" # For logging

        # Plot line WITHOUT label for legend
        ax.plot(tdbs, ws, color=color, linestyle=style, linewidth=linewidth,
                marker='', zorder=5) # Lower zorder than points

        # Add arrow using annotate
        try:
             ax.annotate('', xy=(tdbs[1], ws[1]), xytext=(tdbs[0], ws[0]),
                         arrowprops=dict(arrowstyle="->", color=color, lw=linewidth*0.8), # Slightly thinner arrow
                         va='center', ha='center', zorder=6)
             log.info(f"Plotted process line: {label_desc}")
        except Exception as e:
             log.error(f"Failed to draw arrow for process {label_desc}: {e}")
    else:
        log.debug(f"Skipping process plot from {start_state.label if start_state else 'N/A'} to {end_state.label if end_state else 'N/A'}")
# pages/Manual.py
import streamlit as st

# Optional: Configure the page specifics like title for browser tab
st.set_page_config(page_title="User Manual - Psychro App", layout="wide")

# Add a main title for the page
st.title("📖 User Manual: HVAC Psychrometric Calculator")
st.caption("Version 1.2") # Reflecting current features

st.divider() # Add a visual separator

# Use st.markdown to render the manual content.
# Triple quotes """ allow for multi-line strings easily.
st.markdown("""

## 1. Introduction

Welcome to the HVAC Psychrometric Calculator! This application allows you to:

*   Calculate the thermodynamic properties of moist air based on known conditions using the **Direct Point Calculator**.
*   Simulate common HVAC processes for Air Handling Units (AHUs) and Fan Coil Units (FCUs) via the **Sidebar Configuration**. This includes mixing, cooling, heating, reheat, and steam humidification.
*   Visualize these processes on a standard psychrometric chart.
*   Analyze key performance metrics like coil loads and Sensible Heat Ratio (SHR).
*   Download simulation results to a CSV file.

The application utilizes the robust `psychrolib` library for calculations and `Streamlit` for the interactive user interface.

---

## 2. Getting Started

### Prerequisites

*   Python 3.8 or higher installed.
*   `pip` (Python package installer).
*   Git (Optional, for cloning the project).

### Installation & Running

1.  **Get the Code:**
    *   If you have Git:
        ```bash
        git clone <repository_url>  # Replace with actual URL if applicable
        ```
    *   Otherwise: Download the project files (including the `psychro_app` folder and `📊_Calculator.py`) and place them in a main project directory (e.g., `psychro_project`).

2.  **Navigate to Project Directory:** Open your terminal or command prompt and change directory to the project root (e.g., `psychro_project`). This directory should contain `📊_Calculator.py` and the `psychro_app` folder.
    ```bash
    cd path/to/psychro_project
    ```

3.  **Create & Activate Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Windows:
    venv\\Scripts\\activate.bat
    # macOS/Linux:
    source venv/bin/activate
    ```
    *(You should see `(venv)` at the start of your prompt)*

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Ensure `requirements.txt` is present in the project root)*

5.  **Run the Application:**
    ```bash
    streamlit run 📊_Calculator.py
    ```

Streamlit should automatically open the application in your default web browser. You will see navigation options in the sidebar.

---

## 3. Interface Overview

The application interface is divided into several key areas:

*   **Sidebar (Left):** Always visible. Used for:
    *   Navigating between the main Calculator page and this User Manual.
    *   Configuring the main HVAC simulation (Pressure, System Type, Mode).
    *   Entering simulation parameters within expandable sections.
    *   Triggering the simulation calculation.
*   **Main Area:** Displays the content for the selected page (either the Calculator or this Manual).
    *   **Calculator Page:** Contains the Direct Point Calculator (at the top) and the Simulation Results area (Metrics, Table, Chart).
    *   **Manual Page:** Displays this documentation.

### Calculator Page Layout

*   **Direct Point Calculator (Expander):** Calculate air properties from two inputs.
*   **Results Overview (Metrics):** Quick view of key simulation outputs (Supply Air conditions, Coil Load, SHR).
*   **State Points Table:** Detailed properties for each step in the simulated HVAC process. Includes volumetric flow rates.
*   **Download Button:** Export the State Points Table data to CSV.
*   **Psychrometric Chart (Expander):** Visual representation of the simulated process.

---

## 4. Using the Direct Point Calculator

This tool is located in an expander at the top of the main Calculator page.

1.  **Expand:** Click on "POINT CALCULATOR: Find Air Properties".
2.  **Enter Pressure (Pa):** Input the relevant atmospheric pressure.
3.  **Select Input Pair:** Choose the combination of properties you know (e.g., "Tdb / RH").
4.  **Enter Values:** Input the corresponding values. **Note units:** RH is 0-1 (e.g., 0.5 for 50%), W is kg/kg, h is J/kg.
5.  **Calculate:** Click "Calculate Point Properties".
6.  **View Results:** Calculated properties are displayed in metric cards below the button.

---

## 5. Running an HVAC Simulation

Use the **Sidebar** for configuration and parameter input.

### Step 1: Configure Global Settings

*   **Atmospheric Pressure (Pa):** Set the simulation pressure.

### Step 2: Select System Type & Mode

*   **System Type:** Choose 'AHU' or 'FCU'.
*   **Mode:** Choose 'Cooling' or 'Heating'.

### Step 3: Enter System Parameters

Fill in the details within the collapsible sections (`🌀 Inlet Air`, `💨 Airflow & Fan`, `❄️🔥💧 Conditioning`):

*   **AHU Parameters:** Input OA/RA conditions, Total Mass Flow, OA Fraction, Fan Temp Rise, and parameters for the selected mode (Cooling Coil ADP/BF, Reheat Q, Heating Coil Q). Optionally enable the Steam Humidifier and set the water addition rate (kg/h).
*   **FCU Parameters:** Input Entering Air conditions, Mass Flow, Fan Temp Rise, and parameters for the selected mode (Cooling Coil ADP/BF or Heating Coil Q). *(FCU currently doesn't support Reheat/Humidification in this UI).*

### Step 4: Calculate Results

*   Click the "▶️ Calculate [AHU/FCU] States" button.
*   View results in the main area.

---

## 6. Understanding the Results

Displayed on the main Calculator page after a successful simulation:

*   **Results Overview Metrics:**
    *   *Supply Tdb/RH:* Final air condition.
    *   *Coil Load (kW):* **Positive = Cooling**, **Negative = Heating**. Calculated for the primary coil (Cooling or Heating).
    *   *Coil SHR:* Sensible Heat Ratio for the cooling coil (0-1).
*   **State Points Table:**
    *   Properties at each process step (OA, RA, MA, CC_Out, HC_Out, HUM_Out, SA, etc.).
    *   Includes Volumetric Flow (m³/h & CFM) based on total mass flow and specific volume (V).
*   **Downloading Results (CSV):** Use the "Download Results as CSV" button.
*   **Psychrometric Chart (Expander):**
    *   Shows state points (markers, identified in legend) and process lines (colored arrows).
    *   The legend (outside, top-right) identifies **State Points only**. Process types are inferred from line color/position.

---

## 7. Example Workflow: AHU Cooling Calculation

*(Same example as provided in the text manual - demonstrates steps 1-7 above)*

1.  **Goal:** Cool and dehumidify warm, humid outside air mixed with return air.
2.  **Navigate:** Select the main Calculator page from the sidebar (if not already there).
3.  **Set Pressure (Sidebar):** Use `101325` Pa.
4.  **Select System/Mode (Sidebar):** Choose 'AHU' and 'Cooling'.
5.  **Enter Parameters (Sidebar):**
    *   *Inlet:* OA Tdb=`35.0`, OA RH=`70`. RA Tdb=`24.0`, RA RH=`50`.
    *   *Flow/Fan:* Total Mass Flow=`3.0`, OA Fraction=`25`, Fan Rise=`0.8`.
    *   *Conditioning:* ADP=`11.0`, BF=`0.12`, Reheat=`0`, Humidifier=Unchecked.
6.  **Calculate (Sidebar):** Click "▶️ Calculate AHU States".
7.  **Analyze Results (Main Area):** Review Metrics, Table, and Chart as described in section 6.

---

## 8. Troubleshooting

*   **Sidebar Navigation Missing:** Ensure you created the `pages` directory correctly and placed this `Manual.py` file inside it. Rerun `streamlit run 📊_Calculator.py`. Check Streamlit version (>= 1.10.0).
*   **`ModuleNotFoundError: No module named 'psychro_app'`:** You ran `streamlit run` from the wrong directory. Navigate to the root (`psychro_project`) first.
*   **Calculation Failed / Error Message:** Double-check inputs (units, physical validity). Check pressure. Look for detailed errors in the terminal.
*   **Chart Looks Strange / Empty:** Ensure calculation succeeded. Points might be off the default chart range.

""")
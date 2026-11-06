# Data plan — *SNIFF32*
"If it smells, we can define it"
**Team:** Niklas Etling | Nikita Toporkov | Eemeli Vartio

## Sensors
*   **VOC** (Volatile Organic Compounds)
*   **NH3** (Ammonia)
*   **H2S** (Hydrogen Sulfide)
*   **ETOH** (Ethanol)
*   **ODOR** (Qualitative Pungent Odors)

## Classes 
*Classes will start with simple objects and will be modified as needed (Food, rotten/spoiled, other, etc.).*
*   **Baseline:** Pure classroom air (ambient environment).
*   **Class 1 - Citrus (High VOC):** Smashed orange or lemon peel.
*   **Class 2 - Allium (High H2S/Odor):** Crushed garlic or onion.
*   **Class 3 - Aged Protein (NH3):** Blue cheese and/or deli meat.
*   **Class 4 - Hand Sanitizer (Alcohol/Solvent):** Triggers ETOH, VOC, and ODOR.

## Pre-Processing & Firmware
*   **Firmware Smoothing (DSP):** Implemented a Moving Average filter in the ESP32-S3 C++ code averaging the last 10 analog readings to eliminate high-frequency electrical noise from the ADC before serial output.
*   **Normalization (Delta Calculation):** To combat sensor saturation and long-term drift, all logged data must be recorded as a change from the baseline. The ESP32-S3 or Python script will subtract the immediate pre-exposure baseline from the peak reading (`Delta = Peak Reading - Baseline Air`). **TODO**

## Data Collection Protocol (Concentrated Method)
*Open-air distance measurements will dilute gases and cause the model to learn classroom HVAC drafts. All samples must use a physical gas concentrator (e.g., an inverted plastic cup for solid foods, or a paper cone for transient gases) over the breadboard.*

**Execution Cycle (Repeat for every sample):**
1.  **Purge & Baseline:** Fan the breadboard with a piece of cardboard to clear residual gases. Capture the average clean air reading for 5 seconds to establish the `baseline_air` value for the delta calculation.
2.  **Trap:** Place 'funnel' or inverted cup over the gas-emitting item and the sensor array.
3.  **Concentrate:** Wait 15 to 30 seconds for the gases to build up in the enclosure and allow the sensors to reach a stable peak resistance.
4.  **Sample:** Use a Python script to record 10-15 seconds of the plateaued peak voltages into a CSV file.
5.  **Reset:** Remove the funnel/cup, fan the sensors back to baseline, and repeat.

## Data Processing & ML Features
*   **Uniform Cropping:** In Edge Impulse, the 10-15 second raw CSV recordings will be cropped to uniform 1-to-2-second data windows containing only the stable peak. The dissipation (decay) phase will be excluded to prevent confusion with baseline air.
*   **DSP Block:** The **Flatten** block will extract 4 statistical features (Average, Min, Max, RMS) per sensor, generating a 20-feature array for the ML model.
*   **Machine Learning Model:** Start with a Classical Machine Learning model (Random Forest) for fast training on small datasets, using the EON Tuner to optimize parameters.

## Dataset Split
*   **Training Data:** 80% of collected samples.
*   **Testing/Validation Data:** 20% of collected samples, measured in the exact same environment and identical conditions to verify model accuracy.

## Risks & Mitigations
*   **Unaccounted for venting and airflow of testing environment (Highest Risk):** Mitigated by strict adherence to the funnel/cup concentration method.
*   **Classes with common compounds triggering wrong sensors:** Mitigated by relying on the ML model to map proportional ratios across the array rather than single-sensor spikes.
*   **Sensor heat drift skewing baseline values:** Mitigated by powering the device for a minimum of 15 minutes before testing. 
*   **Sensor Saturation (Stuck Readings):** Pungent gases can permeate the MEMS hotplate. Mitigated by using Delta data calculations and executing a 24-hour "burn-in" (leaving the array powered in clean air) if sensors become severely saturated.
*   **Gas dilution resulting in flat data:** Mitigated by ensuring the sampling enclosure volume remains small.
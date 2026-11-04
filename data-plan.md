# Data plan — *SNIFF32*
"if it smells we can define it"
Niklas Etling Nikita Toporkov Eemeli Vartio


## Sensor
    VOC
    NH3
    H2S
    ETOH
    ODOR

## Classes
Baseline: Pure classroom air (ambient environment).

Class 1 - Citrus (High VOC): Smashed orange or lemon peel.

Class 2 - Allium (High H2S/Odor): Crushed garlic or onion.

Class 3 - Aged Protein (High NH3): Blue cheese or deli meat.

Class 4 - Transient Gas / Fart: Captured gas or novelty fart spray in a sealed ziplock bag to guarantee repeatable concentration.

## Collection
## Data Collection Protocol (Concentrated Method)
*Open-air distance measurements will dilute gases and cause the model to learn classroom HVAC drafts. All samples must use a physical gas concentrator (e.g., an inverted plastic cup for solid foods, or a paper cone for transient gases) over the breadboard.*

# Execution Cycle (Repeat for every sample):

Purge & Baseline: Fan the breadboard with a piece of cardboard to clear residual gases. Record 2 minutes of classroom_air to establish the baseline resistance for that session.

Trap: Place 'funnel' over the gas emitting item and the sensor array.

Concentrate: Wait 15 to 30 seconds for the gases to build up in the enclosure and allow for sensors to register resistance change.

Sample: Python script to record 10-15 second peak voltages from the sensor array into a csv file.

Reset: Repeat with purge and baseline.

## Dataset Split
Training Data: 80% of collected samples.

Testing/Validation Data: 20% of collected samples, measured in the exact same environment and identical conditions to verify model accuracy.

## Risk
    - Sensor heat drift skewing baseline values.
    - Classes with common compounds could trigger the wrong sensors adding noise to measurements
    - Gas dilution resulting in flat data.

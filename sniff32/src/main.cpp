/*
 * ESP32-S3 - DFRobot Fermion MEMS Gas Sensors Test
 * 
 * Sensors:
 * SEN0566 - VOC 
 * SEN0567 - NH3 (Ammonia)
 * SEN0568 - H2S (Hydrogen Sulfide)
 * SEN0569 - EtOH (Ethanol)
 * SEN0571 - Odor
 */

// Define the ESP32-S3 ADC pins connected to the sensors
// Using ADC1 pins (GPIO 1 to 10 are safe for ADC on ESP32-S3)
#include <Arduino.h>


const int pinVOC   = 4;  // SEN0566 Volatile Organic Compounds
const int pinNH3   = 5;  // SEN0567 Ammonia
const int pinH2S   = 6;  // SEN0568 Hydrogen Sulfide
const int pinEtOH  = 7;  // SEN0569 Ethanol 
const int pinOdor  = 8;  // SEN0571 Odor and Gas Detection Sensor

// Define the number of samples to take per sensor
const int NUM_SAMPLES = 10;
const int NUM_SENSORS = 5;

const int sensorPins[NUM_SENSORS] = {pinVOC, pinNH3, pinH2S, pinEtOH, pinOdor};

// 2D array: 5 rows (one for each sensor) and 10 columns (the past readings)
int readings[NUM_SENSORS][NUM_SAMPLES]; 

// read pointer
int readIndex = 0;

// Arrays to keep track of the running sum and the final average for each sensor
long totals[NUM_SENSORS]; 
int averages[NUM_SENSORS];

void setup() {
  Serial.begin(115200);
  delay(1000);
  analogReadResolution(12);
  Serial.println("Starting DFRobot MEMS Gas Sensor Test...");
  
  for (int r = 0; r < NUM_SENSORS; r++ ){ //fill filter buffer with first readings
    totals[r] = 0;
    for (int c = 0; c < NUM_SAMPLES; c++){
      readings[r][c] = analogRead(sensorPins[r]);
      totals[r] += readings[r][c];
    }
  }
  
  // Set the analog resolution to 12 bits (0-4095), default for ESP32
}

void loop() {
  // Read the raw ADC values (0 to 4095)
  // int valVOC  = analogRead(pinVOC);
  // int valNH3  = analogRead(pinNH3);
  // int valH2S  = analogRead(pinH2S);
  // int valEtOH = analogRead(pinEtOH);
  // int valOdor = analogRead(pinOdor);

  // Convert raw values to Voltage (assuming 3.3V reference)
  // float voltVOC  = (valVOC / 4095.0) * 3.3;
  // float voltNH3  = (valNH3 / 4095.0) * 3.3;
  // float voltH2S  = (valH2S / 4095.0) * 3.3;
  // float voltEtOH = (valEtOH / 4095.0) * 3.3;
  // float voltOdor = (valOdor / 4095.0) * 3.3;

// Loop through all 5 sensors
  for (int s = 0; s < NUM_SENSORS; s++) {
    // 1. Subtract the last reading at this position from the total
    totals[s] = totals[s] - readings[s][readIndex]; 
    
    // 2. Read the new raw value from the sensor into the old erased reading index
    readings[s][readIndex] = analogRead(sensorPins[s]); 
    
    // 3. Add the newest reading to the total
    totals[s] = totals[s] + readings[s][readIndex]; 
    
    // 4. Calculate the smoothed average
    averages[s] = totals[s] / NUM_SAMPLES; 
  }

  readIndex = (readIndex + 1) % NUM_SAMPLES;

// Loop through all except the last sensor
  for (int s = 0; s < NUM_SENSORS - 1; s++) {
    Serial.print(averages[s]); 
    Serial.print(",");
  }
  //last sensor with line break
  Serial.println(averages[NUM_SENSORS - 1]);

  // Print voltages to the Serial Monitor (formatted for Serial Plotter)
  // Serial.print("VOC_V:"); Serial.print(voltVOC); Serial.print(", ");
  //Serial.print("NH3_V:"); Serial.print(voltNH3); Serial.print(", ");
  //Serial.print("H2S_V:"); Serial.print(voltH2S); Serial.print(", ");
  //Serial.print("EtOH_V:"); Serial.print(voltEtOH); Serial.print(", ");
  //Serial.print("Odor_V:"); Serial.println(voltOdor);
  // Print voltages to the Serial Monitor (formatted for Serial Plotter)
  // Serial.print(valVOC); Serial.print(","); //VOC
  // Serial.print(valNH3); Serial.print(","); //NH3
  // Serial.print(valH2S); Serial.print(","); //H2S
  // Serial.print(valEtOH); Serial.print(","); //EtOH
  // Serial.println(valOdor); //Odor

  delay(20); // 50Hz
}
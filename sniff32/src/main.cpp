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

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("Starting DFRobot MEMS Gas Sensor Test...");
  
  // Set the analog resolution to 12 bits (0-4095), default for ESP32
  analogReadResolution(12);
}

void loop() {
  // Read the raw ADC values (0 to 4095)
  int valVOC  = analogRead(pinVOC);
  int valNH3  = analogRead(pinNH3);
  int valH2S  = analogRead(pinH2S);
  int valEtOH = analogRead(pinEtOH);
  int valOdor = analogRead(pinOdor);

  // Convert raw values to Voltage (assuming 3.3V reference)
  float voltVOC  = (valVOC / 4095.0) * 3.3;
  float voltNH3  = (valNH3 / 4095.0) * 3.3;
  float voltH2S  = (valH2S / 4095.0) * 3.3;
  float voltEtOH = (valEtOH / 4095.0) * 3.3;
  float voltOdor = (valOdor / 4095.0) * 3.3;


  // Print voltages to the Serial Monitor (formatted for Serial Plotter)
  // Serial.print("VOC_V:"); Serial.print(voltVOC); Serial.print(", ");
  //Serial.print("NH3_V:"); Serial.print(voltNH3); Serial.print(", ");
  //Serial.print("H2S_V:"); Serial.print(voltH2S); Serial.print(", ");
  //Serial.print("EtOH_V:"); Serial.print(voltEtOH); Serial.print(", ");
  //Serial.print("Odor_V:"); Serial.println(voltOdor);
  // Print voltages to the Serial Monitor (formatted for Serial Plotter)
  Serial.print(valVOC); Serial.print(","); //VOC
  Serial.print(valNH3); Serial.print(","); //NH3
  Serial.print(valH2S); Serial.print(","); //H2S
  Serial.print(valEtOH); Serial.print(","); //EtOH
  Serial.println(valOdor); //Odor

  delay(20); // 50Hz
}
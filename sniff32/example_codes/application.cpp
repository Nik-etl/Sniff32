/*
 * Combined Sniff32 measurement application, included by src/main.cpp.
 *
 * Flow:
 *   1. Wait for the external button and show "Ready for Sniffing!".
 *   2. Capture the five sensor values at 50 Hz for the configured duration.
 *   3. Pass the captured window to the classifier placeholder and show its label.
 *   4. Keep the result visible for the configured time, then return to ready.
 *
 * The sample order matches the headerless CSV files:
 * VOC, NH3, H2S, EtOH, Odor.
 */

 // If not in lib add these libraries to the project, these can be found from ArduinoIDE library manager
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

namespace {

// Sensor pins and column order must match the CSV recording sketch.
constexpr uint8_t PIN_VOC = 4;
constexpr uint8_t PIN_NH3 = 5;
constexpr uint8_t PIN_H2S = 6;
constexpr uint8_t PIN_ETOH = 7;
constexpr uint8_t PIN_ODOR = 8;

// Change this to the GPIO used by the external button. Wire the button
// between this pin and GND; INPUT_PULLUP makes a press read LOW.
constexpr uint8_t BUTTON_PIN = 2;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 40;

// Existing display wiring used SDA=8 and SCL=9. Move SDA to GPIO 10 because
// GPIO 8 is also the Odor sensor input; leave SCL on GPIO 9.
constexpr uint8_t OLED_SDA_PIN = 10;
constexpr uint8_t OLED_SCL_PIN = 9;
constexpr uint8_t OLED_ADDRESS = 0x3C;
constexpr int SCREEN_WIDTH = 128;
constexpr int SCREEN_HEIGHT = 64;

// TODO: Set these after choosing the final measurement duration/model window.
constexpr uint32_t MEASUREMENT_DURATION_SECONDS = 10;
constexpr uint32_t RESULT_DISPLAY_SECONDS = 60;

// The sensor sketch samples every 20 ms (approximately 50 Hz).
constexpr uint32_t SAMPLE_INTERVAL_MS = 20;
constexpr uint8_t SENSOR_COUNT = 5;
constexpr uint32_t MEASUREMENT_DURATION_MS =
    MEASUREMENT_DURATION_SECONDS * 1000UL;
constexpr size_t MAX_SAMPLE_COUNT =
    (MEASUREMENT_DURATION_MS + SAMPLE_INTERVAL_MS - 1) / SAMPLE_INTERVAL_MS;

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
float measurement[MAX_SAMPLE_COUNT][SENSOR_COUNT];
size_t measurementSampleCount = 0;

enum class AppState {
  Ready,
  Measuring,
  ShowingResult,
};

AppState appState = AppState::Ready;
uint32_t stateStartedAt = 0;
uint32_t lastSampleAt = 0;
uint32_t lastDisplayedCountdown = 0;
bool rawButtonState = HIGH;
bool stableButtonState = HIGH;
uint32_t buttonStateChangedAt = 0;

void showScreen(const char *line1, const char *line2 = nullptr) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(line1);
  if (line2 != nullptr) {
    display.println(line2);
  }
  display.display();
}

bool buttonWasPressed() {
  const bool reading = digitalRead(BUTTON_PIN);
  const uint32_t now = millis();

  if (reading != rawButtonState) {
    rawButtonState = reading;
    buttonStateChangedAt = now;
  }

  if (now - buttonStateChangedAt >= BUTTON_DEBOUNCE_MS &&
      stableButtonState != rawButtonState) {
    stableButtonState = rawButtonState;
    return stableButtonState == LOW;
  }
  return false;
}

void startMeasurement() {
  measurementSampleCount = 0;
  stateStartedAt = millis();
  lastSampleAt = stateStartedAt - SAMPLE_INTERVAL_MS;
  lastDisplayedCountdown = MEASUREMENT_DURATION_SECONDS;
  appState = AppState::Measuring;

  Serial.printf("Measurement started: %lu seconds\n",
                static_cast<unsigned long>(MEASUREMENT_DURATION_SECONDS));
  char countdownLine[24];
  snprintf(countdownLine, sizeof(countdownLine), "Time left: %lu s",
           static_cast<unsigned long>(MEASUREMENT_DURATION_SECONDS));
  showScreen("Measuring...", countdownLine);
}

void captureAndPrintSample() {
  const float values[SENSOR_COUNT] = {
      static_cast<float>(analogRead(PIN_VOC)),
      static_cast<float>(analogRead(PIN_NH3)),
      static_cast<float>(analogRead(PIN_H2S)),
      static_cast<float>(analogRead(PIN_ETOH)),
      static_cast<float>(analogRead(PIN_ODOR)),
  };

  if (measurementSampleCount < MAX_SAMPLE_COUNT) {
    for (size_t column = 0; column < SENSOR_COUNT; ++column) {
      measurement[measurementSampleCount][column] = values[column];
    }
    ++measurementSampleCount;
  }

  // Keep the emitted measurement rows in the same headerless CSV format.
  for (size_t column = 0; column < SENSOR_COUNT; ++column) {
    Serial.print(values[column], 0);
    Serial.print(column + 1 == SENSOR_COUNT ? '\n' : ',');
  }
}

const char *classifyMeasurement() {
  // TODO: Add the trained model's inferencing header and call the model here.
  // Use `measurement` and `measurementSampleCount` as the captured window,
  // and return the winning model label (for example result.classification[k].label).
  (void)measurement;
  (void)measurementSampleCount;
  return "LABEL PLACEHOLDER";
}

void finishMeasurement() {
  Serial.printf("Measurement finished: %u samples\n",
                static_cast<unsigned>(measurementSampleCount));

  // TODO: Replace the placeholder function with trained-model inference.
  const char *label = classifyMeasurement();
  Serial.printf("Predicted label: %s\n", label);

  showScreen("Measurement done", label);
  stateStartedAt = millis();
  appState = AppState::ShowingResult;
}

void updateMeasurement() {
  const uint32_t now = millis();
  const uint32_t elapsed = now - stateStartedAt;

  if (elapsed >= MEASUREMENT_DURATION_MS) {
    finishMeasurement();
    return;
  }

  const uint32_t remainingSeconds =
      (MEASUREMENT_DURATION_MS - elapsed + 999) / 1000;
  if (remainingSeconds != lastDisplayedCountdown) {
    char countdownLine[24];
    snprintf(countdownLine, sizeof(countdownLine), "Time left: %lu s",
             static_cast<unsigned long>(remainingSeconds));
    showScreen("Measuring...", countdownLine);
    lastDisplayedCountdown = remainingSeconds;
  }

  if (now - lastSampleAt >= SAMPLE_INTERVAL_MS) {
    lastSampleAt = now;
    captureAndPrintSample();
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  rawButtonState = stableButtonState = digitalRead(BUTTON_PIN);
  buttonStateChangedAt = millis();

  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("SSD1306 initialization failed");
    while (true) {
      delay(1000);
    }
  }

  showScreen("Ready for Sniffing!");
  Serial.println("Ready for Sniffing! Press the button to begin.");
}

void loop() {
  const bool pressed = buttonWasPressed();

  switch (appState) {
    case AppState::Ready:
      if (pressed) {
        startMeasurement();
      }
      break;

    case AppState::Measuring:
      updateMeasurement();
      break;

    case AppState::ShowingResult:
      if (millis() - stateStartedAt >= RESULT_DISPLAY_SECONDS * 1000UL) {
        appState = AppState::Ready;
        showScreen("Ready for Sniffing!");
        Serial.println("Ready for Sniffing!");
      }
      break;
  }

  delay(1);
}

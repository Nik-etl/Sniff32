/*
 * SNIFF32 - on-device odor classification (Edge Impulse model).
 *
 * Flow (one button, mirrors the data-collection protocol):
 *   1. Ready         - "Press to baseline". Sensors are sampled continuously at
 *                      50 Hz through the same 10-sample moving average used by
 *                      the recording firmware (example_codes/record.cpp).
 *   2. Baseline      - 5 s average of clean air (skipped if USE_BASELINE_DELTA
 *                      is false).
 *   3. WaitForPeak   - put the cup over the sample; press when readings peak.
 *   4. Measuring     - capture MEASUREMENT_SECONDS of (value - baseline).
 *   5. Classify      - slide the model window (2 s, 500 ms step, as in
 *                      training) over the capture, average class scores.
 *   6. ShowingResult - label + confidence on the OLED; press or wait to reset.
 *
 * Column order everywhere: VOC, NH3, H2S, EtOH, Odor.
 * The recording firmware lives in example_codes/record.cpp.
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <sniff32_inferencing.h>

namespace {

// ── Preprocessing switch ────────────────────────────────────────────────
// true  = feed the model (smoothed value - clean-air baseline), as recorded
//         with `record_live.py -b`.
// false = feed the model absolute smoothed ADC values.
// Must match how the Edge Impulse training data was recorded.
constexpr bool USE_BASELINE_DELTA = true;

// ── Pins ────────────────────────────────────────────────────────────────
constexpr uint8_t SENSOR_COUNT = 5;
constexpr uint8_t SENSOR_PINS[SENSOR_COUNT] = {4, 5, 6, 7, 8};  // VOC, NH3, H2S, EtOH, Odor

constexpr uint8_t BUTTON_PIN = 2;  // button to GND, INPUT_PULLUP
constexpr uint32_t BUTTON_DEBOUNCE_MS = 40;

// GPIO 8 is the Odor sensor, so the OLED uses SDA=10, SCL=9.
constexpr uint8_t OLED_SDA_PIN = 10;
constexpr uint8_t OLED_SCL_PIN = 9;
constexpr uint8_t OLED_ADDRESS = 0x3C;
constexpr int SCREEN_WIDTH = 128;
constexpr int SCREEN_HEIGHT = 64;

// ── Timing ──────────────────────────────────────────────────────────────
constexpr uint32_t SAMPLE_INTERVAL_MS = EI_CLASSIFIER_INTERVAL_MS;  // 20 ms = 50 Hz
constexpr uint32_t BASELINE_SECONDS = 5;
constexpr uint32_t MEASUREMENT_SECONDS = 10;
constexpr uint32_t RESULT_DISPLAY_SECONDS = 60;

constexpr size_t SMOOTHING_SAMPLES = 10;  // same filter as record.cpp

// ── Model window ────────────────────────────────────────────────────────
static_assert(EI_CLASSIFIER_RAW_SAMPLES_PER_FRAME == SENSOR_COUNT,
              "Model expects a different number of sensor axes");
constexpr size_t WINDOW_SAMPLES = EI_CLASSIFIER_RAW_SAMPLE_COUNT;  // 100 = 2 s
constexpr size_t WINDOW_STEP_SAMPLES = 500 / SAMPLE_INTERVAL_MS;   // 500 ms step
constexpr size_t MEASUREMENT_SAMPLES =
    MEASUREMENT_SECONDS * 1000UL / SAMPLE_INTERVAL_MS;
static_assert(MEASUREMENT_SAMPLES >= WINDOW_SAMPLES,
              "Measurement must be at least one model window long");

// ── State ───────────────────────────────────────────────────────────────
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// Moving-average filter (identical maths to record.cpp: integer average).
int filterReadings[SENSOR_COUNT][SMOOTHING_SAMPLES];
long filterTotals[SENSOR_COUNT];
size_t filterIndex = 0;
int smoothed[SENSOR_COUNT];
uint32_t lastSampleAt = 0;

float baseline[SENSOR_COUNT];
double baselineSums[SENSOR_COUNT];
size_t baselineCount = 0;

// Capture, interleaved frame by frame as Edge Impulse expects:
// [VOC0, NH3_0, H2S0, EtOH0, Odor0, VOC1, ...]
float measurement[MEASUREMENT_SAMPLES * SENSOR_COUNT];
size_t measurementCount = 0;
float windowBuffer[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];

enum class AppState { Ready, Baseline, WaitForPeak, Measuring, ShowingResult };
AppState appState = AppState::Ready;
uint32_t stateStartedAt = 0;
uint32_t lastCountdown = 0;

bool rawButtonState = HIGH;
bool stableButtonState = HIGH;
uint32_t buttonChangedAt = 0;

// ── Helpers ─────────────────────────────────────────────────────────────
void showScreen(const char *line1, const char *line2 = nullptr,
                const char *line3 = nullptr) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(line1);
  if (line2) display.println(line2);
  if (line3) display.println(line3);
  display.display();
}

bool buttonWasPressed() {
  const bool reading = digitalRead(BUTTON_PIN);
  const uint32_t now = millis();
  if (reading != rawButtonState) {
    rawButtonState = reading;
    buttonChangedAt = now;
  }
  if (now - buttonChangedAt >= BUTTON_DEBOUNCE_MS &&
      stableButtonState != rawButtonState) {
    stableButtonState = rawButtonState;
    return stableButtonState == LOW;
  }
  return false;
}

void initFilter() {
  for (size_t s = 0; s < SENSOR_COUNT; ++s) {
    filterTotals[s] = 0;
    for (size_t i = 0; i < SMOOTHING_SAMPLES; ++i) {
      filterReadings[s][i] = analogRead(SENSOR_PINS[s]);
      filterTotals[s] += filterReadings[s][i];
    }
    smoothed[s] = filterTotals[s] / SMOOTHING_SAMPLES;
  }
}

void updateFilter() {
  for (size_t s = 0; s < SENSOR_COUNT; ++s) {
    filterTotals[s] -= filterReadings[s][filterIndex];
    filterReadings[s][filterIndex] = analogRead(SENSOR_PINS[s]);
    filterTotals[s] += filterReadings[s][filterIndex];
    smoothed[s] = filterTotals[s] / SMOOTHING_SAMPLES;
  }
  filterIndex = (filterIndex + 1) % SMOOTHING_SAMPLES;
}

void showCountdown(const char *title, uint32_t durationSeconds) {
  const uint32_t elapsed = millis() - stateStartedAt;
  const uint32_t total = durationSeconds * 1000UL;
  const uint32_t remaining = elapsed >= total ? 0 : (total - elapsed + 999) / 1000;
  if (remaining != lastCountdown) {
    char line[24];
    snprintf(line, sizeof(line), "Time left: %lu s", (unsigned long)remaining);
    showScreen(title, line);
    lastCountdown = remaining;
  }
}

void enterState(AppState next) {
  appState = next;
  stateStartedAt = millis();
  lastCountdown = UINT32_MAX;

  switch (next) {
    case AppState::Ready:
      showScreen("Ready for Sniffing!", "",
                 USE_BASELINE_DELTA ? "Press: clean-air base" : "Press: measure");
      Serial.println("Ready. Press the button to start.");
      break;
    case AppState::Baseline:
      for (size_t s = 0; s < SENSOR_COUNT; ++s) baselineSums[s] = 0;
      baselineCount = 0;
      Serial.println("Recording clean-air baseline...");
      break;
    case AppState::WaitForPeak:
      showScreen("Baseline locked", "Cover sample + wait", "Press at peak");
      Serial.println("Cover the sample; press the button when readings peak.");
      break;
    case AppState::Measuring:
      measurementCount = 0;
      Serial.println("Measuring...");
      break;
    case AppState::ShowingResult:
      break;
  }
}

// Runs the model over every 2 s window (500 ms step) and averages the scores.
void classifyMeasurement() {
  showScreen("Classifying...");

  float scoreSums[EI_CLASSIFIER_LABEL_COUNT] = {0};
  size_t windows = 0;

  for (size_t start = 0; start + WINDOW_SAMPLES <= measurementCount;
       start += WINDOW_STEP_SAMPLES) {
    memcpy(windowBuffer, &measurement[start * SENSOR_COUNT],
           sizeof(windowBuffer));

    signal_t signal;
    if (numpy::signal_from_buffer(windowBuffer,
                                  EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE,
                                  &signal) != 0) {
      Serial.println("signal_from_buffer failed");
      continue;
    }

    ei_impulse_result_t result = {0};
    const EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
    if (err != EI_IMPULSE_OK) {
      Serial.printf("run_classifier failed (%d)\n", err);
      continue;
    }

    Serial.printf("window %u:", (unsigned)windows);
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; ++i) {
      scoreSums[i] += result.classification[i].value;
      Serial.printf(" %s=%.2f", result.classification[i].label,
                    result.classification[i].value);
    }
    Serial.println();
    ++windows;
  }

  if (windows == 0) {
    showScreen("Classify failed", "See serial log");
    Serial.println("No windows classified.");
    enterState(AppState::ShowingResult);
    return;
  }

  size_t best = 0;
  for (size_t i = 1; i < EI_CLASSIFIER_LABEL_COUNT; ++i) {
    if (scoreSums[i] > scoreSums[best]) best = i;
  }
  const char *label = ei_classifier_inferencing_categories[best];
  const float confidence = scoreSums[best] / windows;

  Serial.printf("Result: %s (%.0f%% over %u windows)\n", label,
                confidence * 100.0f, (unsigned)windows);

  char confLine[24];
  snprintf(confLine, sizeof(confLine), "%.0f%% confident", confidence * 100.0f);
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("It smells like:");
  display.setTextSize(2);
  display.setCursor(0, 20);
  display.println(label);
  display.setTextSize(1);
  display.setCursor(0, 48);
  display.println(confLine);
  display.display();

  enterState(AppState::ShowingResult);
}

// Same headerless CSV line as record.cpp: VOC,NH3,H2S,EtOH,Odor (smoothed ADC).
void printSensorRow() {
  Serial.printf("%d,%d,%d,%d,%d\n", smoothed[0], smoothed[1], smoothed[2],
                smoothed[3], smoothed[4]);
}

// Called once per 20 ms sample, after the filter has been updated.
void onSample() {
  switch (appState) {
    case AppState::Baseline:
      for (size_t s = 0; s < SENSOR_COUNT; ++s) baselineSums[s] += smoothed[s];
      ++baselineCount;
      break;

    case AppState::Measuring:
      if (measurementCount < MEASUREMENT_SAMPLES) {
        float *frame = &measurement[measurementCount * SENSOR_COUNT];
        for (size_t s = 0; s < SENSOR_COUNT; ++s) {
          frame[s] = USE_BASELINE_DELTA ? smoothed[s] - baseline[s]
                                        : static_cast<float>(smoothed[s]);
        }
        ++measurementCount;
      }
      break;

    default:
      break;
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  rawButtonState = stableButtonState = digitalRead(BUTTON_PIN);
  buttonChangedAt = millis();

  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("SSD1306 initialization failed");
    while (true) delay(1000);
  }

  Serial.printf("Model: %u labels, window %u samples x %u axes @ %u Hz\n",
                (unsigned)EI_CLASSIFIER_LABEL_COUNT, (unsigned)WINDOW_SAMPLES,
                (unsigned)EI_CLASSIFIER_RAW_SAMPLES_PER_FRAME,
                (unsigned)EI_CLASSIFIER_FREQUENCY);

  initFilter();
  lastSampleAt = millis();
  enterState(AppState::Ready);
}

void loop() {
  const bool pressed = buttonWasPressed();
  const uint32_t now = millis();

  // Keep the filter warm in every state, at the training sample rate.
  if (now - lastSampleAt >= SAMPLE_INTERVAL_MS) {
    lastSampleAt += SAMPLE_INTERVAL_MS;
    if (now - lastSampleAt >= SAMPLE_INTERVAL_MS) lastSampleAt = now;  // resync after stalls
    updateFilter();
    onSample();
    // Stream live values between measurements; keep quiet while capturing.
    if (appState != AppState::Measuring) printSensorRow();
  }

  switch (appState) {
    case AppState::Ready:
      if (pressed) {
        enterState(USE_BASELINE_DELTA ? AppState::Baseline : AppState::Measuring);
      }
      break;

    case AppState::Baseline:
      showCountdown("Clean-air baseline", BASELINE_SECONDS);
      if (millis() - stateStartedAt >= BASELINE_SECONDS * 1000UL &&
          baselineCount > 0) {
        Serial.print("Baseline:");
        for (size_t s = 0; s < SENSOR_COUNT; ++s) {
          baseline[s] = baselineSums[s] / baselineCount;
          Serial.printf(" %.1f", baseline[s]);
        }
        Serial.println();
        enterState(AppState::WaitForPeak);
      }
      break;

    case AppState::WaitForPeak:
      if (pressed) enterState(AppState::Measuring);
      break;

    case AppState::Measuring:
      showCountdown("Measuring...", MEASUREMENT_SECONDS);
      if (measurementCount >= MEASUREMENT_SAMPLES) classifyMeasurement();
      break;

    case AppState::ShowingResult:
      if (pressed ||
          millis() - stateStartedAt >= RESULT_DISPLAY_SECONDS * 1000UL) {
        enterState(AppState::Ready);
      }
      break;
  }

  delay(1);
}

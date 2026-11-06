## ESP32-S3 code

# 10-point moving average filter tradeoffs
    This should smooth out analog voltage readings however may introduce delay, especially at the beginning of sensor cycle; 
    when the device is first powered on, the filter buffer fills with initial sensor readings. This will cause the initial high readings of the gas sensors as they calibrate to the environment reach baseline slower. 
    
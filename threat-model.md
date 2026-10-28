## Sniff32 Class Project Esp32 threat Assessment

**Asset:**
The primary assets that require protection include the proprietary TinyML sniffing model intellectual property and the personal data associated with the Edge Impulse account. Additionally, the ESP32 device's access to the local area network (LAN) is a critical resource that must be safeguarded against unauthorized use.

**Threat:**
The main threats to the Sniff32 project come from competitors within the product segment attempting to steal the model IP. Malicious actors could also compromise the system through direct physical access or network-based Wi-Fi attacks, with the risk significantly amplified by any failure to encrypt key information.

**Response:**
To mitigate these risks, physical access to the ESP32 and its sensor array must be strictly secured. Before deployment, especially since physical access may be easy in environments like retail stores, the device should be hardened with three layers of security: data-at-rest encryption, flash encryption, and secure boot. While secure network authentication must be adopted for connected deployments, simple data-at-rest encryption may be sufficient if the device is not configured to use Wi-Fi.
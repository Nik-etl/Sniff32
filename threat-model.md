## Sniff32 Class Project Esp32 threat Assessment

**Asset:** The sniffing model tiny ML IP. Edge Impulse personal data. Access to LAN through the device.

**Threat:** Competitor in the product segment. Attacks through physical access and Wi-Fi network. Failure to encrypt key information. 

**Response:** Physical access to the esp32 and the sensor array  should be secured. Before deployment, the device should be hardened with all 3 layers (Data at rest, Flash encryption, and secure boot) because attacker's access may be easy depending on deployment location (stores). We should adopt secure network authentication but if the device is not configured to use Wi-Fi, simple data-at-rest encryption is sufficient. 
# PiFire Home Assistant Integration

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-blue)](https://www.home-assistant.io/)
[![GitHub release](https://img.shields.io/github/v/release/yourname/pifire-ha)](https://github.com/yourname/pifire-ha/releases)

A **custom integration** for [Home Assistant](https://www.home-assistant.io/) that connects to the [PiFire pellet grill controller](https://github.com/nebhead/PiFire) created by [**@nebhead**](https://github.com/nebhead).  

This integration lets you view real-time grill and probe data inside Home Assistant and control your grill using PiFire’s **High-Level API commands**.

📚 Official PiFire documentation is available here:  
👉 [PiFire Docs](https://nebhead.github.io/PiFire-Pages/)

---

## ✨ Features

- ✅ Live grill temperature sensor  
- ✅ Probe 1 & Probe 2 temperature sensors  
- ✅ Pellet level and pellet type sensors  
- ✅ Current grill mode, status, and units  
- ✅ Control grill setpoints & notify temps  
- ✅ One-click buttons for **Startup**, **Shutdown**, and **Prime**  
- ✅ Mode selector (Stop / Smoke / Hold / Monitor, etc.)  
- ✅ [Planned] Auto-discovery via Zeroconf & MQTT  

---

## 📂 File Structure

The integration lives under:
```
config/
└── custom_components/
└── pifire/
├── init.py
├── manifest.json
├── const.py
├── config_flow.py
├── sensor.py
├── number.py
├── select.py
├── switch.py
├── button.py
├── diagnostics.py
├── strings.json
└── translations/
└── en.json
```

---

## 🚀 Installation

1. Navigate to your Home Assistant **`config/custom_components/`** folder.  
   If the folder doesn’t exist, create it.

2. Clone or download this repo into a folder named **`pifire`**:

   ```bash
   cd config/custom_components
   git clone https://github.com/voidlock/pifire-ha.git pifire

## Font Attribution

This project’s logo uses the [Orbitron](https://www.theleagueofmoveabletype.com/orbitron) font by Matt McInerney, licensed under the [SIL Open Font License](https://scripts.sil.org/OFL).

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


# Owon-Multimeter-Manager
Advanced GUI software (PyQt5) for real-time control, data acquisition, CSV logging, and chart analysis for the OWON XDM2041 digital multimeter (SCPI/VISA communication).

# Owon Multimeter Manager for XDM2041

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)

GUI tool for controlling and logging data from the OWON XDM2041 bench multimeter. Implements SCPI protocol over USB/serial via PyVISA.

## Core Capabilities
- **Bilingual UI:** English and Polish support.
- **Connection Handling:** Native OS COM port detection, baud rate, and parity configuration.
- **SCPI Commands:** Control measurement modes (VDC, VAC, RES, TEMP), ranges, polling rates, and math functions (NULL, dB, dBm, AVERage).
- **Data Visualization (PyQtGraph):**
  - Real-time signal plotting with crosshairs.
  - Measurement distribution histogram.
  - Signal derivative (dV/dt) for noise/spike detection.
- **Logging:** Background CSV datalogging at custom intervals.
- **Hardware Integration:** Direct readout of statistical buffers and RTC.

## Requirements
- Python 3.7+
- OWON XDM2041 via USB.
- Virtual COM port drivers (manufacturer provided).

## Installation

```bash
git clone [https://github.com/YOUR_USERNAME/owon-multimeter-manager.git](https://github.com/YOUR_USERNAME/owon-multimeter-manager.git)
cd owon-multimeter-manager

# Create and activate virtual environment
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

# Install strictly required dependencies
pip install PyQt5 pyqtgraph pyvisa pyserial numpy
```
Usage
Power on the XDM2041 and connect via USB.

##Execute the application:
 - python OMM_XDM2041.py
 - Connect XDM Multimeter
 - After succesful connection click "Pause/Resume" button

##for Windows
 - Download exe file and run
 - Connect XDM Multimeter
 - After succesful connection click "Pause/Resume" button
   

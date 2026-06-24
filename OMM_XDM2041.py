import sys
import time
import csv
import math
import json
import os
import logging
import bisect
import threading
from typing import Optional, Tuple, Dict, List

import numpy as np
import pyvisa
import pyqtgraph as pg
import serial.tools.list_ports  # Przywrócone dla systemowych nazw portów
from pyvisa.errors import VisaIOError
from pyvisa.constants import Parity, StopBits

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QComboBox, QPushButton, QLabel, QMessageBox,
    QGroupBox, QGridLayout, QProgressBar, QDoubleSpinBox,
    QFileDialog, QCheckBox, QSpinBox, QTabWidget, QSplitter
)
# POPRAWKA PYINSTALLER: Unikamy bezpośredniego importu 'Qt', aby statyczna analiza AST działała poprawnie
from PyQt5 import QtCore
from PyQt5.QtCore import QTimer, QThread, pyqtSignal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MODERN_STYLE = """
QMainWindow { background-color: #1e1e1e; color: #d4d4d4; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
QWidget { color: #d4d4d4; }
QGroupBox { border: 1px solid #3a3a3a; border-radius: 6px; margin-top: 15px; font-weight: bold; color: #569cd6; background-color: #252526; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 5px; }
QPushButton { background-color: #0e639c; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-weight: bold; }
QPushButton:hover { background-color: #1177bb; }
QPushButton:pressed { background-color: #094771; }
QPushButton:disabled { background-color: #4d4d4d; color: #8a8a8a; }
QPushButton[btn_type="danger"] { background-color: #c62828; }
QPushButton[btn_type="danger"]:hover { background-color: #e53935; }
QPushButton[btn_type="success"] { background-color: #2e7d32; }
QPushButton[btn_type="success"]:hover { background-color: #43a047; }
QComboBox, QSpinBox, QDoubleSpinBox { background-color: #333333; color: #d4d4d4; border: 1px solid #444444; padding: 4px; border-radius: 3px; }
QComboBox::drop-down { border: 0px; }
QTabWidget::pane { border: 1px solid #3a3a3a; border-radius: 4px; background: #252526; }
QTabBar::tab { background: #2d2d2d; color: #969696; padding: 8px 15px; border: 1px solid #3a3a3a; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background: #1e1e1e; color: #569cd6; font-weight: bold; border-top: 2px solid #569cd6; }
QProgressBar { border: 1px solid #444; background-color: #222; border-radius: 3px; text-align: center; }
QProgressBar::chunk { background-color: #ff9800; width: 5px; margin: 0.5px; }
"""

SCPI_MODES: Dict[str, str] = {
    "VDC": "CONFigure:VOLTage:DC", "VAC": "CONFigure:VOLTage:AC",
    "IDC": "CONFigure:CURRent:DC", "IAC": "CONFigure:CURRent:AC",
    "RES2W": "CONFigure:RESistance", "RES4W": "CONFigure:FRESistance",
    "CAP": "CONFigure:CAPacitance", "FREQ": "CONFigure:FREQuency",
    "PER": "CONFigure:PERiod", "TEMP": "CONFigure:TEMPerature:RTD",
    "DIODE": "CONFigure:DIODe", "CONT": "CONFigure:CONTinuity"
}
SCPI_RATES: Dict[str, str] = {"F": "F", "M": "M", "L": "L"}
DB_REFS: List[str] = ["50", "75", "93", "110", "124", "125", "135", "150", "250", "300", "500", "600", "800", "900", "1000", "1200", "8000"]
HV_THRESHOLD: float = 30.0
SETTINGS_FILE: str = "settings.json"

LANGS: Dict[str, Dict[str, str]] = {
    "PL": {
        "title": "OWON XDM2041 - Studio Analityczne", "tab_conn": "Połączenie", "tab_meas": "Pomiar", "tab_adv": "Zaawansowane",
        "btn_toggle_com": "Przełącz Panel", "grp_conn": "Konfiguracja Portu COM", "lbl_port": "Port:", "btn_refresh": "Odśwież",
        "btn_connect": "Połącz", "btn_disconnect": "Rozłącz", "btn_reset": "Reset (*RST)", "grp_config": "Parametry Główne",
        "lbl_mode": "Tryb SCPI:", "lbl_rate": "Szybkość:", "lbl_math": "F. Matematyczna:", "chk_auto_range": "Auto-Range",
        "lbl_range": "Zakres (1-7):", "chk_beeper": "Beeper", "chk_dual_display": "Dual Display", "chk_scientific": "Format naukowy (e)",
        "grp_adv": "Kompensacja & RTD", "lbl_cont": "Ciągłość:", "lbl_temp_unit": "Jedn. Temp:", "lbl_temp_sens": "Typ RTD:",
        "lbl_temp_show": "Wyśw. Temp:", "lbl_db_ref": "Baza dB/dBm:", "lbl_null_offset": "Offset NULL:", "btn_apply_adv": "Aplikuj Ustawienia",
        "grp_log": "Datalogger CSV", "lbl_interval": "Interwał zapisu [s]:", "btn_log_start": "Start LOG", "btn_log_stop": "Zatrzymaj LOG",
        "btn_pause": "Pauza / Wznów Zapis", "btn_new_curve": "Nowy Cykl Pomiaru", "btn_clear": "Wyczyść Pamięć", "lbl_time": "Czas [s]",
        "lang_switch": "EN", "err_port": "Brak wybranego portu COM.", "err_conn": "Błąd połączenia VISA:\n", "err_visa": "Utracono komunikację z miernikiem.",
        "msg_conn": "Zidentyfikowano: ", "grp_hardware": "Statystyki Miernika", "btn_get_stats": "Pobierz STATS (Hardware)", "btn_get_rtc": "Czas RTC",
        "lbl_hw_stats": "Miernik: ---", "lbl_rtc": "Zegar: ---", "msg_avg_only": "Wymagany tryb matematyczny AVERage.",
        "grp_plot_stats_global": "Analiza Globalna", "grp_plot_stats_region": "Analiza Zaznaczenia (A-B)", "lbl_plot_min": "MIN: ---",
        "lbl_plot_max": "MAX: ---", "lbl_plot_avg": "AVG: ---", "lbl_timebase": "Okno X [s] (0=Całość):", "lbl_sampling_rate": "Polling [ms]:",
        "lbl_max_points": "Bufor max:", "grp_pass_fail": "Limity Pass/Fail (Test)", "chk_enable_limits": "Aktywuj", "lbl_upper_limit": "Górny Limit:",
        "lbl_lower_limit": "Dolny Limit:", "lbl_status_pass": "PASS", "lbl_status_fail": "FAIL", "lbl_status_idle": "---",
        "title_main_plot": "Sygnał Główny", "title_hist_plot": "Histogram Rozkładu", "title_deriv_plot": "Szybkość Zmian (dV/dt)", "lbl_counts": "Ilość zliczeń (n)",

        "tt_conn": "Sekcja konfiguracji portu szeregowego. Wybierz odpowiedni port COM z systemu i parametry zgodne z miernikiem (np. 115200 8N1).",
        "tt_meas": "Główne parametry: tryb pracy (np. VDC), szybkość odpytywania (RATE) oraz funkcje matematyczne sprzętowe.",
        "tt_pf": "Ustaw limity testowe. Przekroczenie limitów (Upper/Lower) ustawi kolorowy wskaźnik na status FAIL.",
        "tt_adv": "Zaawansowane: Kompensacja rezystancji dla pomiaru ciągłości, typ czujnika RTD oraz offset matematyczny (NULL).",
        "tt_log": "Datalogger: Zapisuje w tle bieżące pomiary do wybranego pliku CSV z zadanym interwałem czasowym.",
        "tt_hw": "Zewnętrzne statystyki sprzętowe: Pobiera bufory prosto z elektroniki miernika (działa tylko gdy F. Matematyczna = AVERage).",
        "tt_plot_main": "Główny wykres pomiarowy. Ruszaj myszą, aby aktywować interaktywny kursor wartości. Użyj PPM, by skalować oś Y.",
        "tt_plot_hist": "Histogram: Pokazuje gęstość i częstotliwość występowania konkretnych wartości (np. szum pomiarowy).",
        "tt_plot_deriv": "Pochodna sygnału (dV/dt): Wykres pomocny w łapaniu szybkich szpilek napięcia i analizy stromości trendu."
    },
    "EN": {
        "title": "OWON XDM2041 - Analytical Studio", "tab_conn": "Connection", "tab_meas": "Measurement", "tab_adv": "Advanced",
        "btn_toggle_com": "Toggle Panel", "grp_conn": "COM Port Setup", "lbl_port": "Port:", "btn_refresh": "Refresh", "btn_connect": "Connect",
        "btn_disconnect": "Disconnect", "btn_reset": "Reset (*RST)", "grp_config": "Main Settings", "lbl_mode": "SCPI Mode:",
        "lbl_rate": "Rate:", "lbl_math": "Math Func:", "chk_auto_range": "Auto-Range", "lbl_range": "Range (1-7):", "chk_beeper": "Beeper",
        "chk_dual_display": "Dual Display", "chk_scientific": "Scientific (e)", "grp_adv": "Compensation & RTD", "lbl_cont": "Continuity:",
        "lbl_temp_unit": "Temp Unit:", "lbl_temp_sens": "RTD Sensor:", "lbl_temp_show": "Temp View:", "lbl_db_ref": "dB/dBm Ref:",
        "lbl_null_offset": "NULL Offset:", "btn_apply_adv": "Apply Settings", "grp_log": "CSV Datalogger", "lbl_interval": "Log Interval [s]:",
        "btn_log_start": "Start Logging", "btn_log_stop": "Stop Logging", "btn_pause": "Pause / Resume", "btn_new_curve": "New Cycle",
        "btn_clear": "Clear Memory", "lbl_time": "Time [s]", "lang_switch": "PL", "err_port": "No valid COM port selected.",
        "err_conn": "VISA connection error:\n", "err_visa": "Communication lost.", "msg_conn": "Connected: ", "grp_hardware": "Hardware Stats",
        "btn_get_stats": "Fetch Device STATS", "btn_get_rtc": "Read RTC", "lbl_hw_stats": "Device: ---", "lbl_rtc": "Clock: ---",
        "msg_avg_only": "AVERage math mode required.", "grp_plot_stats_global": "Global Analysis", "grp_plot_stats_region": "Region Analysis (A-B)",
        "lbl_plot_min": "MIN: ---", "lbl_plot_max": "MAX: ---", "lbl_plot_avg": "AVG: ---", "lbl_timebase": "X Window [s] (0=All):",
        "lbl_sampling_rate": "Polling [ms]:", "lbl_max_points": "Max Buffer:", "grp_pass_fail": "Pass/Fail Limits", "chk_enable_limits": "Enable",
        "lbl_upper_limit": "Upper Limit:", "lbl_lower_limit": "Lower Limit:", "lbl_status_pass": "PASS", "lbl_status_fail": "FAIL",
        "lbl_status_idle": "---", "title_main_plot": "Primary Signal", "title_hist_plot": "Distribution Histogram",
        "title_deriv_plot": "Rate of Change (dV/dt)", "lbl_counts": "Hit Count (n)",

        "tt_conn": "Serial port configuration section. Choose the correct COM port and matching parameters (e.g., 115200 8N1).",
        "tt_meas": "Primary measurement options: SCPI mode (e.g. VDC), polling RATE, and hardware Math functions.",
        "tt_pf": "Set test boundaries. If the measurement exceeds Upper/Lower limits, the status indicator will show FAIL.",
        "tt_adv": "Advanced: Resistance compensation (Continuity), RTD sensor type, and base Math offset (NULL).",
        "tt_log": "Datalogger: Saves incoming measurements in the background to a selected CSV file at a given interval.",
        "tt_hw": "Hardware statistics: Fetches internal device buffer arrays (requires Math mode to be set to AVERage).",
        "tt_plot_main": "Main measurement chart. Hover the mouse over the chart to display the crosshair tooltip. Right-click to scale.",
        "tt_plot_hist": "Histogram: Displays measurement value distribution, showing how often certain values (like noise) occur.",
        "tt_plot_deriv": "Derivative chart (dV/dt): Extremely useful for catching sudden voltage spikes and signal trends."
    }
}

class AcquisitionThread(QThread):
    data_ready = pyqtSignal(str)
    error_occurred = pyqtSignal()

    def __init__(self, instrument, lock, parent=None):
        super().__init__(parent)
        self.instrument = instrument
        self.lock = lock
        self.interval_ms = 200
        self.is_running = False

    def run(self):
        self.is_running = True
        while self.is_running:
            start_time = time.time()
            if self.instrument:
                with self.lock:
                    try:
                        raw_response = self.instrument.query("MEAS?").strip()
                        if raw_response:
                            self.data_ready.emit(raw_response)
                    except VisaIOError:
                        self.error_occurred.emit()

            elapsed = (time.time() - start_time) * 1000
            sleep_time = max(10, self.interval_ms - elapsed)
            self.msleep(int(sleep_time))

    def stop(self):
        self.is_running = False
        self.wait()

class DiagnosticDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        # Set default language to EN as requested
        self.current_lang: str = "EN"
        self.resource_manager = pyvisa.ResourceManager()
        self.instrument: Optional[pyvisa.resources.MessageBasedResource] = None
        self.visa_lock = threading.Lock()
        self.acquisition_thread: Optional[AcquisitionThread] = None
        self.consecutive_errors: int = 0

        self.is_logging_active: bool = False
        self.csv_file_handle = None
        self.csv_writer = None
        self.last_log_timestamp: float = 0.0

        self.timestamps: List[float] = []
        self.readings: List[float] = []
        self.deriv_timestamps: List[float] = []
        self.deriv_readings: List[float] = []

        self.session_start_time: float = time.time()
        self.plot_sum: float = 0.0
        self.plot_min: float = float('inf')
        self.plot_max: float = float('-inf')

        self.help_icons_list = []
        self.plot_titles = []

        self._init_ui()
        self._init_plot_elements()

        self._refresh_serial_ports()
        self._toggle_hardware_controls(False)
        self._load_saved_configuration()
        self._apply_translations()

    def _create_help_icon(self, tooltip_key: str) -> QLabel:
        """Creates a unified information icon with an assigned tooltip key."""
        lbl = QLabel("?")
        lbl.setFixedSize(16, 16)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setStyleSheet("""
            QLabel {
                background-color: #555555; color: #ffffff; border-radius: 8px;
                font-size: 11px; font-weight: bold; border: 1px solid #666666;
            }
            QLabel:hover { background-color: #777777; border: 1px solid #999999; }
        """)
        self.help_icons_list.append((lbl, tooltip_key))
        return lbl

    def _init_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.control_panel = QWidget()
        self.control_panel.setFixedWidth(320)
        control_layout = QVBoxLayout(self.control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)

        top_bar = QHBoxLayout()
        self.btn_lang = QPushButton()
        self.btn_lang.setFixedWidth(40)
        self.btn_lang.clicked.connect(self._switch_language)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_lang)
        control_layout.addLayout(top_bar)

        self.tabs = QTabWidget()
        self.tab_conn = QWidget()
        self.tab_meas = QWidget()
        self.tab_adv = QWidget()

        self.tabs.addTab(self.tab_conn, "")
        self.tabs.addTab(self.tab_meas, "")
        self.tabs.addTab(self.tab_adv, "")
        control_layout.addWidget(self.tabs)

        self._build_connection_tab(self.tab_conn)
        self._build_measurement_tab(self.tab_meas)
        self._build_advanced_tab(self.tab_adv)
        self._build_lcd_display(control_layout)

        self.charts_splitter = QSplitter(QtCore.Qt.Vertical)
        self.main_chart_container = QWidget()
        main_chart_layout = QVBoxLayout(self.main_chart_container)
        main_chart_layout.setContentsMargins(0,0,0,0)

        self._build_plot_controls(main_chart_layout)

        pg.setConfigOption('background', '#1e1e1e')
        pg.setConfigOption('foreground', '#d4d4d4')

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        main_chart_layout.addWidget(self._wrap_plot(self.plot_widget, "title_main_plot", "tt_plot_main"))
        self.charts_splitter.addWidget(self.main_chart_container)

        self.bottom_charts_splitter = QSplitter(QtCore.Qt.Horizontal)
        self.hist_widget = pg.PlotWidget()
        self.hist_widget.showGrid(x=True, y=True, alpha=0.3)
        self.bottom_charts_splitter.addWidget(self._wrap_plot(self.hist_widget, "title_hist_plot", "tt_plot_hist"))

        self.deriv_widget = pg.PlotWidget()
        self.deriv_widget.showGrid(x=True, y=True, alpha=0.3)
        self.bottom_charts_splitter.addWidget(self._wrap_plot(self.deriv_widget, "title_deriv_plot", "tt_plot_deriv"))

        self.charts_splitter.addWidget(self.bottom_charts_splitter)
        self.charts_splitter.setSizes([600, 200])

        main_layout.addWidget(self.control_panel)
        main_layout.addWidget(self.charts_splitter, stretch=1)
        self.setCentralWidget(central_widget)

    def _wrap_plot(self, plot_widget, title_key, tooltip_key):
        """Embeds the plot component in a layout equipped with a title Label and a ? sign."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 0)

        header = QHBoxLayout()
        title_lbl = QLabel()
        title_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #569cd6;")
        self.plot_titles.append((title_lbl, title_key))

        header.addWidget(title_lbl)
        header.addWidget(self._create_help_icon(tooltip_key))
        header.addStretch()

        layout.addLayout(header)
        layout.addWidget(plot_widget)
        # Remove the default built-in title rendering by PyQtGraph
        plot_widget.setTitle(None)
        return container

    def _build_connection_tab(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        self.conn_group = QGroupBox()
        grid = QGridLayout(self.conn_group)

        # Adding a help icon to the GroupBox (top-right)
        grid.addWidget(self._create_help_icon("tt_conn"), 0, 2, alignment=QtCore.Qt.AlignRight)

        self.lbl_port = QLabel()
        self.port_selector = QComboBox()
        self.baud_selector = QComboBox()
        self.baud_selector.addItems(["4800", "9600", "19200", "38400", "57600", "115200"])
        self.data_bits_selector = QComboBox()
        self.data_bits_selector.addItems(["7", "8"])
        self.parity_selector = QComboBox()
        self.parity_selector.addItems(["None", "Odd", "Even"])
        self.stop_bits_selector = QComboBox()
        self.stop_bits_selector.addItems(["1", "2"])

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton()
        self.btn_refresh.clicked.connect(self._refresh_serial_ports)
        self.btn_connect = QPushButton()
        self.btn_connect.setProperty("btn_type", "success")
        self.btn_connect.clicked.connect(self._establish_connection)
        self.btn_disconnect = QPushButton()
        self.btn_disconnect.setProperty("btn_type", "danger")
        self.btn_disconnect.clicked.connect(self._terminate_connection)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_disconnect)

        grid.addWidget(self.lbl_port, 0, 0)
        grid.addWidget(self.port_selector, 0, 1)
        grid.addWidget(QLabel("Baudrate:"), 1, 0)
        grid.addWidget(self.baud_selector, 1, 1)
        grid.addWidget(QLabel("Data Bits:"), 2, 0)
        grid.addWidget(self.data_bits_selector, 2, 1)
        grid.addWidget(QLabel("Parity:"), 3, 0)
        grid.addWidget(self.parity_selector, 3, 1)
        grid.addWidget(QLabel("Stop Bits:"), 4, 0)
        grid.addWidget(self.stop_bits_selector, 4, 1)

        layout.addWidget(self.conn_group)
        layout.addLayout(btn_layout)

        self.btn_reset = QPushButton()
        self.btn_reset.clicked.connect(self._send_reset_command)
        layout.addWidget(self.btn_reset)

        self.hw_group = QGroupBox()
        hw_layout = QVBoxLayout(self.hw_group)

        # Header with help
        h_hw = QHBoxLayout()
        h_hw.addStretch()
        h_hw.addWidget(self._create_help_icon("tt_hw"))
        hw_layout.addLayout(h_hw)

        self.btn_get_stats = QPushButton()
        self.btn_get_stats.clicked.connect(self._fetch_hardware_statistics)
        self.lbl_hw_stats = QLabel("---")
        self.btn_get_rtc = QPushButton()
        self.btn_get_rtc.clicked.connect(self._fetch_real_time_clock)
        self.lbl_rtc = QLabel("---")

        hw_layout.addWidget(self.btn_get_stats)
        hw_layout.addWidget(self.lbl_hw_stats)
        hw_layout.addWidget(self.btn_get_rtc)
        hw_layout.addWidget(self.lbl_rtc)
        layout.addWidget(self.hw_group)
        layout.addStretch()

    def _build_measurement_tab(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        self.config_group = QGroupBox()
        grid = QGridLayout(self.config_group)

        grid.addWidget(self._create_help_icon("tt_meas"), 0, 2, alignment=QtCore.Qt.AlignRight)

        self.lbl_mode = QLabel()
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(SCPI_MODES.keys())
        self.mode_selector.currentIndexChanged.connect(self._handle_mode_change)

        self.lbl_rate = QLabel()
        self.rate_selector = QComboBox()
        self.rate_selector.addItems(SCPI_RATES.keys())
        self.rate_selector.currentIndexChanged.connect(self._schedule_device_sync)

        self.lbl_math = QLabel()
        self.math_selector = QComboBox()
        self.math_selector.addItems(["OFF", "NULL", "DB", "DBM", "AVERage"])
        self.math_selector.currentIndexChanged.connect(self._schedule_device_sync)

        self.chk_auto_range = QCheckBox()
        self.chk_auto_range.setChecked(True)
        self.chk_auto_range.toggled.connect(self._handle_autorange_toggle)

        self.lbl_range = QLabel()
        self.range_selector = QComboBox()
        self.range_selector.addItems(["1", "2", "3", "4", "5", "6", "7"])
        self.range_selector.currentIndexChanged.connect(self._schedule_device_sync)

        self.chk_beeper = QCheckBox()
        self.chk_beeper.setChecked(True)
        self.chk_beeper.toggled.connect(self._schedule_device_sync)

        self.chk_dual_display = QCheckBox()
        self.chk_dual_display.toggled.connect(self._schedule_device_sync)

        self.chk_scientific = QCheckBox()
        self.chk_scientific.toggled.connect(self._force_display_refresh)

        grid.addWidget(self.lbl_mode, 0, 0)
        grid.addWidget(self.mode_selector, 0, 1)
        grid.addWidget(self.lbl_rate, 1, 0)
        grid.addWidget(self.rate_selector, 1, 1)
        grid.addWidget(self.lbl_math, 2, 0)
        grid.addWidget(self.math_selector, 2, 1)
        grid.addWidget(self.chk_auto_range, 3, 0, 1, 2)
        grid.addWidget(self.lbl_range, 4, 0)
        grid.addWidget(self.range_selector, 4, 1)
        grid.addWidget(self.chk_beeper, 5, 0, 1, 2)
        grid.addWidget(self.chk_dual_display, 6, 0, 1, 2)
        grid.addWidget(self.chk_scientific, 7, 0, 1, 2)

        layout.addWidget(self.config_group)

        self.pf_group = QGroupBox()
        pf_grid = QGridLayout(self.pf_group)
        pf_grid.addWidget(self._create_help_icon("tt_pf"), 0, 2, alignment=QtCore.Qt.AlignRight)

        self.chk_enable_limits = QCheckBox()
        self.chk_enable_limits.toggled.connect(self._update_pf_region)

        self.lbl_upper_limit = QLabel()
        self.limit_max_spin = QDoubleSpinBox()
        self.limit_max_spin.setRange(-1e9, 1e9)
        self.limit_max_spin.setDecimals(5)
        self.limit_max_spin.valueChanged.connect(self._update_pf_region)

        self.lbl_lower_limit = QLabel()
        self.limit_min_spin = QDoubleSpinBox()
        self.limit_min_spin.setRange(-1e9, 1e9)
        self.limit_min_spin.setDecimals(5)
        self.limit_min_spin.valueChanged.connect(self._update_pf_region)

        pf_grid.addWidget(self.chk_enable_limits, 0, 0, 1, 2)
        pf_grid.addWidget(self.lbl_upper_limit, 1, 0)
        pf_grid.addWidget(self.limit_max_spin, 1, 1)
        pf_grid.addWidget(self.lbl_lower_limit, 2, 0)
        pf_grid.addWidget(self.limit_min_spin, 2, 1)

        layout.addWidget(self.pf_group)
        layout.addStretch()

    def _build_advanced_tab(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        self.adv_group = QGroupBox()
        grid = QGridLayout(self.adv_group)

        grid.addWidget(self._create_help_icon("tt_adv"), 0, 2, alignment=QtCore.Qt.AlignRight)

        self.lbl_cont = QLabel()
        self.cont_threshold_spin = QSpinBox()
        self.cont_threshold_spin.setRange(1, 1000)

        self.lbl_temp_unit = QLabel()
        self.temp_unit_selector = QComboBox()
        self.temp_unit_selector.addItems(["C", "F", "K"])

        self.lbl_temp_sens = QLabel()
        self.temp_type_selector = QComboBox()
        self.temp_type_selector.addItems(["PT100", "KITS90"])

        self.lbl_temp_show = QLabel()
        self.temp_show_selector = QComboBox()
        self.temp_show_selector.addItems(["ALL", "TEMP", "MEAS"])

        self.lbl_db_ref = QLabel()
        self.db_ref_selector = QComboBox()
        self.db_ref_selector.addItems(DB_REFS)

        self.lbl_null_offset = QLabel()
        self.null_offset_spin = QDoubleSpinBox()
        self.null_offset_spin.setRange(-1e6, 1e6)
        self.null_offset_spin.setDecimals(5)

        self.btn_apply_adv = QPushButton()
        self.btn_apply_adv.clicked.connect(self._schedule_device_sync)

        grid.addWidget(self.lbl_cont, 0, 0)
        grid.addWidget(self.cont_threshold_spin, 0, 1)
        grid.addWidget(self.lbl_temp_unit, 1, 0)
        grid.addWidget(self.temp_unit_selector, 1, 1)
        grid.addWidget(self.lbl_temp_sens, 2, 0)
        grid.addWidget(self.temp_type_selector, 2, 1)
        grid.addWidget(self.lbl_temp_show, 3, 0)
        grid.addWidget(self.temp_show_selector, 3, 1)
        grid.addWidget(self.lbl_db_ref, 4, 0)
        grid.addWidget(self.db_ref_selector, 4, 1)
        grid.addWidget(self.lbl_null_offset, 5, 0)
        grid.addWidget(self.null_offset_spin, 5, 1)
        grid.addWidget(self.btn_apply_adv, 6, 0, 1, 2)
        layout.addWidget(self.adv_group)

        self.log_group = QGroupBox()
        log_grid = QGridLayout(self.log_group)
        log_grid.addWidget(self._create_help_icon("tt_log"), 0, 2, alignment=QtCore.Qt.AlignRight)

        self.lbl_interval = QLabel()
        self.log_interval_spin = QDoubleSpinBox()
        self.log_interval_spin.setRange(0.1, 3600.0)

        self.btn_log_toggle = QPushButton()
        self.btn_log_toggle.setCheckable(True)
        self.btn_log_toggle.clicked.connect(self._toggle_csv_logging)

        log_grid.addWidget(self.lbl_interval, 0, 0)
        log_grid.addWidget(self.log_interval_spin, 0, 1)
        log_grid.addWidget(self.btn_log_toggle, 1, 0, 1, 2)
        layout.addWidget(self.log_group)
        layout.addStretch()

    def _build_lcd_display(self, parent_layout: QVBoxLayout):
        self.lbl_hv_warning = QLabel("⚠ HIGH VOLTAGE")
        self.lbl_hv_warning.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff5252; background-color: #3e2723; padding: 5px; border-radius: 4px;")
        self.lbl_hv_warning.setVisible(False)
        self.lbl_hv_warning.setAlignment(QtCore.Qt.AlignCenter)

        self.lbl_current_val = QLabel("---")
        self.lbl_current_val.setStyleSheet("font-size: 32px; font-weight: bold; color: #aeea00; background-color: #121212; padding: 15px; border: 2px solid #333; border-radius: 6px;")
        self.lbl_current_val.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.lbl_pf_indicator = QLabel("---")
        self.lbl_pf_indicator.setStyleSheet("font-size: 22px; font-weight: bold; color: #555;")
        self.lbl_pf_indicator.setAlignment(QtCore.Qt.AlignCenter)

        self.barmeter = QProgressBar()
        self.barmeter.setTextVisible(False)
        self.barmeter.setRange(0, 1000)
        self.barmeter.setFixedHeight(12)

        parent_layout.addWidget(self.lbl_hv_warning)
        parent_layout.addWidget(self.lbl_current_val)
        parent_layout.addWidget(self.barmeter)
        parent_layout.addWidget(self.lbl_pf_indicator)

    def _build_plot_controls(self, parent_layout: QVBoxLayout):
        ctrl_layout = QHBoxLayout()

        self.plot_stats_group = QGroupBox()
        stats_layout = QHBoxLayout(self.plot_stats_group)
        stats_layout.setContentsMargins(5,5,5,5)
        self.lbl_plot_min = QLabel()
        self.lbl_plot_max = QLabel()
        self.lbl_plot_avg = QLabel()
        self.lbl_plot_min.setStyleSheet("color: #4da6ff; font-weight: bold;")
        self.lbl_plot_max.setStyleSheet("color: #ff4d4d; font-weight: bold;")
        self.lbl_plot_avg.setStyleSheet("color: #ffd700; font-weight: bold;")
        stats_layout.addWidget(self.lbl_plot_min)
        stats_layout.addWidget(self.lbl_plot_max)
        stats_layout.addWidget(self.lbl_plot_avg)
        ctrl_layout.addWidget(self.plot_stats_group)

        controls_box = QGroupBox()
        controls_layout = QHBoxLayout(controls_box)
        controls_layout.setContentsMargins(5,5,5,5)

        self.lbl_timebase = QLabel()
        self.timebase_spin = QSpinBox()
        self.timebase_spin.setRange(0, 100000)

        self.lbl_sampling_rate = QLabel()
        self.sampling_rate_spin = QSpinBox()
        self.sampling_rate_spin.setRange(100, 60000)
        self.sampling_rate_spin.setSingleStep(50)
        self.sampling_rate_spin.setValue(200)
        self.sampling_rate_spin.valueChanged.connect(self._update_timer_interval)

        self.lbl_max_points = QLabel()
        self.max_points_spin = QSpinBox()
        self.max_points_spin.setRange(0, 1000000)
        self.max_points_spin.setSingleStep(1000)
        self.max_points_spin.setValue(10000)

        controls_layout.addWidget(self.lbl_timebase)
        controls_layout.addWidget(self.timebase_spin)
        controls_layout.addWidget(self.lbl_sampling_rate)
        controls_layout.addWidget(self.sampling_rate_spin)
        controls_layout.addWidget(self.lbl_max_points)
        controls_layout.addWidget(self.max_points_spin)
        ctrl_layout.addWidget(controls_box)

        btn_layout = QHBoxLayout()
        self.btn_start_stop = QPushButton()
        self.btn_start_stop.clicked.connect(self._toggle_sampling_state)
        self.btn_new_curve = QPushButton()
        self.btn_new_curve.clicked.connect(self._initialize_new_plot_curve)
        self.btn_clear = QPushButton()
        self.btn_clear.setProperty("btn_type", "danger")
        self.btn_clear.clicked.connect(self._reset_plot_data)

        btn_layout.addWidget(self.btn_start_stop)
        btn_layout.addWidget(self.btn_new_curve)
        btn_layout.addWidget(self.btn_clear)
        ctrl_layout.addLayout(btn_layout)

        parent_layout.addLayout(ctrl_layout)

    def _init_plot_elements(self):
        self.active_plot_curve = self.plot_widget.plot(pen=pg.mkPen(color='#aeea00', width=2))
        self.min_marker = pg.ScatterPlotItem(size=12, pen=pg.mkPen(None), brush=pg.mkBrush(77, 166, 255, 255))
        self.max_marker = pg.ScatterPlotItem(size=12, pen=pg.mkPen(None), brush=pg.mkBrush(255, 77, 77, 255))
        self.plot_widget.addItem(self.min_marker)
        self.plot_widget.addItem(self.max_marker)

        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('y', style=QtCore.Qt.DashLine))
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('y', style=QtCore.Qt.DashLine))
        self.crosshair_label = pg.TextItem(anchor=(1, 1), color='y', fill=(0, 0, 0, 150))
        self.plot_widget.addItem(self.crosshair_v, ignoreBounds=True)
        self.plot_widget.addItem(self.crosshair_h, ignoreBounds=True)
        self.plot_widget.addItem(self.crosshair_label, ignoreBounds=True)
        self.proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self._mouse_moved_event)

        self.region_selector = pg.LinearRegionItem(brush=(50, 50, 200, 50))
        self.region_selector.setZValue(-10)
        self.region_selector.hide()
        self.plot_widget.addItem(self.region_selector)
        self.region_selector.sigRegionChanged.connect(self._calculate_region_statistics)

        self.pf_region = pg.LinearRegionItem(orientation='horizontal', movable=False, brush=pg.mkBrush(46, 125, 50, 60), pen=pg.mkPen('#ff5252', width=2))
        self.pf_region.setZValue(-15)
        self.pf_region.hide()
        self.plot_widget.addItem(self.pf_region)

        self.hist_curve = pg.PlotCurveItem(x=np.array([0, 1]), y=np.array([0, 0]), fillLevel=0, brush=(77, 166, 255, 100), pen='#4da6ff')
        self.hist_widget.addItem(self.hist_curve)

        self.hist_crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('y', style=QtCore.Qt.DashLine))
        self.hist_crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('y', style=QtCore.Qt.DashLine))
        self.hist_crosshair_label = pg.TextItem(anchor=(1, 1), color='y', fill=(0, 0, 0, 150))
        self.hist_widget.addItem(self.hist_crosshair_v, ignoreBounds=True)
        self.hist_widget.addItem(self.hist_crosshair_h, ignoreBounds=True)
        self.hist_widget.addItem(self.hist_crosshair_label, ignoreBounds=True)
        self.hist_proxy = pg.SignalProxy(self.hist_widget.scene().sigMouseMoved, rateLimit=60, slot=self._hist_mouse_moved_event)

        self.deriv_curve = self.deriv_widget.plot(pen=pg.mkPen(color='#ff5252', width=1.5))

        self.deriv_crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('y', style=QtCore.Qt.DashLine))
        self.deriv_crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('y', style=QtCore.Qt.DashLine))
        self.deriv_crosshair_label = pg.TextItem(anchor=(1, 1), color='y', fill=(0, 0, 0, 150))
        self.deriv_widget.addItem(self.deriv_crosshair_v, ignoreBounds=True)
        self.deriv_widget.addItem(self.deriv_crosshair_h, ignoreBounds=True)
        self.deriv_widget.addItem(self.deriv_crosshair_label, ignoreBounds=True)
        self.deriv_proxy = pg.SignalProxy(self.deriv_widget.scene().sigMouseMoved, rateLimit=60, slot=self._deriv_mouse_moved_event)


    def _update_pf_region(self, *_):
        if self.chk_enable_limits.isChecked():
            val_min = self.limit_min_spin.value()
            val_max = self.limit_max_spin.value()
            self.pf_region.setRegion([min(val_min, val_max), max(val_min, val_max)])
            self.pf_region.show()
        else:
            self.pf_region.hide()

    def _fetch_hardware_statistics(self):
        if not self.instrument: return
        t = LANGS.get(self.current_lang, LANGS["EN"])

        if self.math_selector.currentText() != "AVERage":
            QMessageBox.information(self, "Info", t["msg_avg_only"])
            return

        thread_was_running = self.acquisition_thread and self.acquisition_thread.is_running
        if thread_was_running:
            self.acquisition_thread.stop()

        with self.visa_lock:
            try:
                original_timeout = self.instrument.timeout
                self.instrument.timeout = 5000
                self._clear_visa_buffer()
                time.sleep(0.3)

                raw_stats = self.instrument.query("CALCulate:AVERage:ALL?").strip()
                self.instrument.timeout = original_timeout

                parts = raw_stats.split(',')
                if len(parts) == 4:
                    min_val, max_val, avg_val, count_val = float(parts[0]), float(parts[1]), float(parts[2]), int(float(parts[3]))
                    self.lbl_hw_stats.setText(f"MIN: {min_val:.4e} | MAX: {max_val:.4e} | AVG: {avg_val:.4e} | CNT: {count_val}")
                else:
                    self.lbl_hw_stats.setText("Parse ERROR")

            except VisaIOError as e:
                logging.error(f"Timeout while fetching hardware statistics: {e}")
                self.lbl_hw_stats.setText("Error: Timeout")
                self._clear_visa_buffer()

        if thread_was_running:
            self.acquisition_thread.start()

    def _fetch_real_time_clock(self):
        if not self.instrument: return
        t = LANGS.get(self.current_lang, LANGS["EN"])

        thread_was_running = self.acquisition_thread and self.acquisition_thread.is_running
        if thread_was_running:
            self.acquisition_thread.stop()

        with self.visa_lock:
            try:
                original_timeout = self.instrument.timeout
                self.instrument.timeout = 5000
                self._clear_visa_buffer()
                time.sleep(0.3)

                device_date = self.instrument.query("SYSTem:DATE?").strip()
                device_time = self.instrument.query("SYSTem:TIME?").strip()

                self.instrument.timeout = original_timeout
                prefix = t['lbl_rtc'].split(':')[0]
                self.lbl_rtc.setText(f"{prefix}: {device_date} {device_time}")

            except VisaIOError as e:
                logging.error(f"Timeout while fetching RTC: {e}")
                self.lbl_rtc.setText("RTC Error")
                self._clear_visa_buffer()

        if thread_was_running:
            self.acquisition_thread.start()

    def _clear_visa_buffer(self):
        if not self.instrument: return
        try:
            self.instrument.clear()
        except VisaIOError as e:
            logging.debug(f"Skipped buffer clearing error: {e}")

    def _switch_language(self):
        self.current_lang = "EN" if self.current_lang == "PL" else "PL"
        self._apply_translations()

    def _handle_autorange_toggle(self, is_checked: bool):
        self.range_selector.setEnabled(not is_checked)
        self._schedule_device_sync()

    def _force_display_refresh(self):
        if self.readings:
            self._update_lcd_and_barmeter(self.readings[-1], None, self.mode_selector.currentText())
            self._display_plot_statistics(self.plot_min, self.plot_max, self.plot_sum / len(self.readings), mode="GLOBAL")

    def _update_timer_interval(self, val: int):
        if self.acquisition_thread:
            self.acquisition_thread.interval_ms = val

    def _toggle_hardware_controls(self, is_enabled: bool):
        controls = [
            self.mode_selector, self.rate_selector, self.math_selector,
            self.chk_auto_range, self.chk_beeper, self.chk_dual_display,
            self.chk_scientific, self.cont_threshold_spin, self.temp_unit_selector,
            self.temp_type_selector, self.temp_show_selector, self.db_ref_selector,
            self.null_offset_spin, self.btn_apply_adv, self.btn_get_stats,
            self.btn_get_rtc, self.btn_start_stop, self.btn_clear,
            self.btn_new_curve, self.btn_log_toggle, self.log_interval_spin,
            self.sampling_rate_spin, self.max_points_spin, self.chk_enable_limits,
            self.limit_max_spin, self.limit_min_spin
        ]
        for ctrl in controls:
            ctrl.setEnabled(is_enabled)

        self.range_selector.setEnabled(is_enabled and not self.chk_auto_range.isChecked())
        if is_enabled: self._update_dynamic_ui_constraints()

        self.port_selector.setEnabled(not is_enabled)
        self.baud_selector.setEnabled(not is_enabled)
        self.data_bits_selector.setEnabled(not is_enabled)
        self.parity_selector.setEnabled(not is_enabled)
        self.stop_bits_selector.setEnabled(not is_enabled)
        self.btn_refresh.setEnabled(not is_enabled)
        self.btn_reset.setEnabled(is_enabled)

    def _update_dynamic_ui_constraints(self):
        selected_mode = self.mode_selector.currentText()
        is_ac_mode = "AC" in selected_mode
        self.chk_dual_display.setEnabled(is_ac_mode)
        if not is_ac_mode: self.chk_dual_display.setChecked(False)

        is_voltage_mode = "V" in selected_mode
        current_math = self.math_selector.currentText()

        self.math_selector.blockSignals(True)
        self.math_selector.clear()
        available_math_options = ["OFF", "NULL", "AVERage"]
        if is_voltage_mode: available_math_options.extend(["DB", "DBM"])
        self.math_selector.addItems(available_math_options)

        if current_math in available_math_options:
            self.math_selector.setCurrentText(current_math)
        else:
            self.math_selector.setCurrentIndex(0)
        self.math_selector.blockSignals(False)

        is_temp_mode = "TEMP" in selected_mode
        self.temp_unit_selector.setEnabled(is_temp_mode)
        self.temp_type_selector.setEnabled(is_temp_mode)
        self.temp_show_selector.setEnabled(is_temp_mode)

        is_cont_mode = "CONT" in selected_mode
        self.cont_threshold_spin.setEnabled(is_cont_mode)

    def _refresh_serial_ports(self):
        self.port_selector.clear()
        # Restoring COM port polling from the pyserial hardware list
        ports = serial.tools.list_ports.comports()
        if not ports:
            self.port_selector.addItem("No COM devices found", None)
        else:
            for port in ports:
                # Friendly system name "COM3 - USB Serial Port", but we send "COM3" to PyVISA
                self.port_selector.addItem(f"{port.device} - {port.description}", port.device)

    def _establish_connection(self):
        device_port = self.port_selector.currentData()
        translations = LANGS.get(self.current_lang, LANGS["EN"])
        if not device_port:
            QMessageBox.warning(self, "Warning", translations["err_port"])
            return

        try:
            self.instrument = self.resource_manager.open_resource(device_port)
            self._configure_serial_parameters()
            self.instrument.write("SYSTem:REMote")
            time.sleep(0.1)
            device_id = self.instrument.query("*IDN?").strip()
            logging.info(f"Connected to: {device_id}")

            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self._toggle_hardware_controls(True)

            self.acquisition_thread = AcquisitionThread(self.instrument, self.visa_lock)
            self.acquisition_thread.interval_ms = self.sampling_rate_spin.value()
            self.acquisition_thread.data_ready.connect(self._process_acquisition_cycle)
            self.acquisition_thread.error_occurred.connect(self._handle_communication_error)

            self._handle_mode_change()

        except VisaIOError as e:
            logging.error(f"IO Error: {e}")
            QMessageBox.critical(self, "Error", f"{translations['err_conn']}{e}")
            self._terminate_connection()

    def _configure_serial_parameters(self):
        if not self.instrument: return
        self.instrument.baud_rate = int(self.baud_selector.currentText())
        self.instrument.data_bits = int(self.data_bits_selector.currentText())
        parity_selection = self.parity_selector.currentText()
        if "Odd" in parity_selection: self.instrument.parity = Parity.odd
        elif "Even" in parity_selection: self.instrument.parity = Parity.even
        else: self.instrument.parity = Parity.none
        self.instrument.stop_bits = StopBits.one if self.stop_bits_selector.currentText() == "1" else StopBits.two
        self.instrument.read_termination = '\n'
        self.instrument.write_termination = '\n'
        self.instrument.timeout = 2000

    def _terminate_connection(self):
        if self.acquisition_thread:
            self.acquisition_thread.stop()

        self._disable_region_analysis()
        if self.btn_log_toggle.isChecked():
            self.btn_log_toggle.setChecked(False)
            self._toggle_csv_logging()

        if self.instrument:
            with self.visa_lock:
                try:
                    self.instrument.write("SYSTem:LOCal")
                    self.instrument.close()
                except VisaIOError as e:
                    logging.debug(f"Skipped error while disconnecting: {e}")
            self.instrument = None

        self.lbl_current_val.setText("---")
        self.barmeter.setValue(0)
        self.lbl_pf_indicator.setText(LANGS[self.current_lang]["lbl_status_idle"])
        self.lbl_pf_indicator.setStyleSheet("color: #555;")
        self.lbl_hv_warning.setVisible(False)
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self._toggle_hardware_controls(False)

    def _send_reset_command(self):
        if not self.instrument: return
        if self.acquisition_thread:
            self.acquisition_thread.stop()

        self._disable_region_analysis()

        with self.visa_lock:
            try:
                self.instrument.write("*RST")
                QTimer.singleShot(1500, self._handle_mode_change)
            except VisaIOError as e:
                logging.error(f"RST Error: {e}")

    def _handle_mode_change(self):
        if not self.instrument: return
        if self.acquisition_thread and self.acquisition_thread.is_running:
            self.acquisition_thread.stop()

        self._disable_region_analysis()
        self._update_dynamic_ui_constraints()

        mode_name = self.mode_selector.currentText()
        scpi_command = SCPI_MODES.get(mode_name, "CONFigure:VOLTage:DC")

        with self.visa_lock:
            try:
                self.instrument.write(scpi_command)
                self._update_y_axis_label()
                QTimer.singleShot(600, self._schedule_device_sync)
            except VisaIOError as e:
                logging.error(f"Mode Change Error: {e}")
                self._terminate_connection()

    def _schedule_device_sync(self):
        if not self.instrument: return
        thread_was_running = self.acquisition_thread and self.acquisition_thread.is_running
        if thread_was_running:
            self.acquisition_thread.stop()

        self._update_y_axis_label()
        QTimer.singleShot(300, lambda: self._sync_configuration_to_device(thread_was_running))

    def _sync_configuration_to_device(self, resume_sampling: bool):
        if not self.instrument: return
        with self.visa_lock:
            try:
                self._clear_visa_buffer()
                rate = SCPI_RATES.get(self.rate_selector.currentText(), "M")
                self.instrument.write(f"RATE {rate}")
                beeper_state = "ON" if self.chk_beeper.isChecked() else "OFF"
                self.instrument.write(f"SYSTem:BEEPer:STATe {beeper_state}")

                if self.chk_auto_range.isChecked(): self.instrument.write("AUTO")
                else: self.instrument.write(f"RANGE {self.range_selector.currentText()}")

                if self.chk_dual_display.isEnabled() and self.chk_dual_display.isChecked():
                    self.instrument.write('FUNCtion2 "FREQuency"')
                else:
                    self.instrument.write('FUNCtion2 "NONe"')

                self._apply_math_configuration()
                self._apply_advanced_configuration()
            except VisaIOError as e:
                logging.error(f"Sync Config Error: {e}")

        if resume_sampling and self.acquisition_thread:
            self.acquisition_thread.start()

    def _apply_math_configuration(self):
        math_mode = self.math_selector.currentText()
        if math_mode in ["OFF", "Brak"]:
            self.instrument.write("CALCulate:STATe OFF")
            return

        # Initialization of the math function
        self.instrument.write(f"CALCulate:FUNCtion {math_mode}")
        time.sleep(0.1)  # CRITICAL TIME (Pacing). Reduction of parser Race Condition after switching from OFF

        if math_mode in ["DB", "DBM"]:
            self.instrument.write(f"CALCulate:{math_mode}:REFerence {self.db_ref_selector.currentText()}")
        elif math_mode == "NULL":
            offset = self.null_offset_spin.value()
            self.instrument.write(f"CALCulate:NULL:OFFSet {offset:.5f}")
            time.sleep(0.1) # CRITICAL TIME. The meter must initialize the buffer value before enabling the state

        self.instrument.write("CALCulate:STATe ON")
        time.sleep(0.1) # The last element calming the UART parser of the meter

    def _apply_advanced_configuration(self):
        if self.temp_unit_selector.isEnabled():
            unit = self.temp_unit_selector.currentText().replace('°', '')
            self.instrument.write(f"SENSe:TEMPerature:RTD:UNIT {unit}")
            self.instrument.write(f"SENSe:TEMPerature:RTD:TYPe {self.temp_type_selector.currentText()}")
            self.instrument.write(f"SENSe:TEMPerature:RTD:SHOW {self.temp_show_selector.currentText()}")
        if self.cont_threshold_spin.isEnabled():
            self.instrument.write(f"SENSe:CONTinuity:THREshold {self.cont_threshold_spin.value()}")

    def _process_acquisition_cycle(self, raw_response: str):
        try:
            mode_name = self.mode_selector.currentText()
            primary_val, secondary_val = self._parse_scpi_measurement(raw_response)
            primary_val = self._apply_local_math_transformations(primary_val)

            pf_status = self._process_pass_fail(primary_val)

            self._update_lcd_and_barmeter(primary_val, secondary_val, mode_name)
            self._append_data_to_plot(primary_val)
            self._handle_csv_logging(primary_val, mode_name, pf_status)

            self.consecutive_errors = 0

        except ValueError as e:
            logging.warning(f"Parse Error from instrument: {e}")

    def _parse_scpi_measurement(self, raw_string: str) -> Tuple[float, Optional[float]]:
        if "," in raw_string:
            parts = raw_string.split(",")
            return float(parts[0]), float(parts[1])
        return float(raw_string), None

    def _apply_local_math_transformations(self, reading: float) -> float:
        math_mode = self.math_selector.currentText()
        if math_mode == "NULL": return reading - self.null_offset_spin.value()
        return reading

    def _process_pass_fail(self, val: float) -> str:
        t = LANGS.get(self.current_lang, LANGS["EN"])
        if not self.chk_enable_limits.isChecked():
            self.lbl_pf_indicator.setText(t["lbl_status_idle"])
            self.lbl_pf_indicator.setStyleSheet("color: #555;")
            return "N/A"

        ul = self.limit_max_spin.value()
        ll = self.limit_min_spin.value()

        if val > ul or val < ll:
            self.lbl_pf_indicator.setText(t["lbl_status_fail"])
            self.lbl_pf_indicator.setStyleSheet("color: #ff5252; font-weight: bold;")
            return "FAIL"
        else:
            self.lbl_pf_indicator.setText(t["lbl_status_pass"])
            self.lbl_pf_indicator.setStyleSheet("color: #aeea00; font-weight: bold;")
            return "PASS"

    def _update_lcd_and_barmeter(self, primary_val: float, secondary_val: Optional[float], mode_name: str):
        if secondary_val is not None:
            txt = f"MAIN: {self._format_scientific_string(primary_val)}\nSUB: {self._format_scientific_string(secondary_val)}"
        else:
            txt = f"{self._format_scientific_string(primary_val)}"

        self.lbl_current_val.setText(txt)
        abs_val = abs(primary_val)
        if abs_val < 1e-9:
            self.barmeter.setValue(0)
        else:
            magnitude = 10 ** math.floor(math.log10(abs_val) + 1)
            self.barmeter.setValue(int((abs_val / magnitude) * 1000))

        is_high_voltage = "V" in mode_name and abs_val >= HV_THRESHOLD and self.math_selector.currentText() not in ["DB", "DBM"]
        self.lbl_hv_warning.setVisible(is_high_voltage)

    def _format_scientific_string(self, val: float) -> str:
        if self.chk_scientific.isChecked(): return f"{val:.5e}"
        formatted = f"{val:.8f}"
        return formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted

    def _handle_communication_error(self):
        self.consecutive_errors += 1
        if self.consecutive_errors > 2:
            self._terminate_connection()
            t = LANGS.get(self.current_lang, LANGS["EN"])
            QMessageBox.warning(self, "Error", t["err_visa"])
            self.consecutive_errors = 0
        else:
            self._clear_visa_buffer()

    def _append_data_to_plot(self, reading: float):
        current_t = time.time() - self.session_start_time
        self.timestamps.append(current_t)
        self.readings.append(reading)

        if len(self.readings) > 1:
            dt = current_t - self.timestamps[-2]
            if dt > 0.0001:
                dvdt = (reading - self.readings[-2]) / dt
                self.deriv_timestamps.append(current_t)
                self.deriv_readings.append(dvdt)

        max_pts = self.max_points_spin.value()

        if max_pts > 0 and len(self.readings) > max_pts:
            dropped_val = self.readings.pop(0)
            self.timestamps.pop(0)
            self.plot_sum -= dropped_val

            if self.deriv_readings:
                self.deriv_readings.pop(0)
                self.deriv_timestamps.pop(0)

            if dropped_val == self.plot_min or dropped_val == self.plot_max:
                self.plot_min = min(self.readings) if self.readings else float('inf')
                self.plot_max = max(self.readings) if self.readings else float('-inf')
                try:
                    self.min_marker.setData([self.timestamps[self.readings.index(self.plot_min)]], [self.plot_min])
                    self.max_marker.setData([self.timestamps[self.readings.index(self.plot_max)]], [self.plot_max])
                except ValueError: pass

        self.plot_sum += reading

        if reading < self.plot_min:
            self.plot_min = reading
            self.min_marker.setData([current_t], [reading])

        if reading > self.plot_max:
            self.plot_max = reading
            self.max_marker.setData([current_t], [reading])

        avg_val = self.plot_sum / len(self.readings) if self.readings else 0.0
        self._display_plot_statistics(self.plot_min, self.plot_max, avg_val, mode="GLOBAL")
        self.active_plot_curve.setData(self.timestamps, self.readings)

        self.deriv_curve.setData(self.deriv_timestamps, self.deriv_readings)

        if len(self.readings) > 5:
            counts, edges = np.histogram(self.readings, bins='auto')
            centers = (edges[:-1] + edges[1:]) / 2
            self.hist_curve.setData(x=centers, y=counts)

        window_size = self.timebase_spin.value()
        if window_size > 0:
            if current_t > window_size:
                self.plot_widget.setXRange(current_t - window_size, current_t, padding=0)
                self.deriv_widget.setXRange(current_t - window_size, current_t, padding=0)
            else:
                self.plot_widget.setXRange(0, window_size, padding=0)
                self.deriv_widget.setXRange(0, window_size, padding=0)
        else:
            self.plot_widget.enableAutoRange(axis=pg.ViewBox.XAxis)
            self.deriv_widget.enableAutoRange(axis=pg.ViewBox.XAxis)

    def _mouse_moved_event(self, event_args):
        pos = event_args[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            x_val = mouse_point.x()
            if not self.timestamps: return

            idx = bisect.bisect_left(self.timestamps, x_val)
            if idx > 0 and idx < len(self.timestamps):
                if abs(x_val - self.timestamps[idx-1]) < abs(x_val - self.timestamps[idx]):
                    idx = idx - 1
            elif idx >= len(self.timestamps):
                idx = len(self.timestamps) - 1

            actual_x = self.timestamps[idx]
            actual_y = self.readings[idx]

            self.crosshair_v.setPos(actual_x)
            self.crosshair_h.setPos(actual_y)
            self.crosshair_label.setPos(actual_x, actual_y)
            self.crosshair_label.setText(f"T: {actual_x:.2f}s\nV: {self._format_scientific_string(actual_y)}")

    def _hist_mouse_moved_event(self, event_args):
        pos = event_args[0]
        if self.hist_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.hist_widget.plotItem.vb.mapSceneToView(pos)
            x_val = mouse_point.x()
            y_val = mouse_point.y()

            self.hist_crosshair_v.setPos(x_val)
            self.hist_crosshair_h.setPos(y_val)
            self.hist_crosshair_label.setPos(x_val, y_val)
            self.hist_crosshair_label.setText(f"V: {self._format_scientific_string(x_val)}\nN: {int(max(0, y_val))}")

    def _deriv_mouse_moved_event(self, event_args):
        pos = event_args[0]
        if self.deriv_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.deriv_widget.plotItem.vb.mapSceneToView(pos)
            x_val = mouse_point.x()
            if not self.deriv_timestamps: return

            idx = bisect.bisect_left(self.deriv_timestamps, x_val)
            if idx > 0 and idx < len(self.deriv_timestamps):
                if abs(x_val - self.deriv_timestamps[idx-1]) < abs(x_val - self.deriv_timestamps[idx]):
                    idx = idx - 1
            elif idx >= len(self.deriv_timestamps):
                idx = len(self.deriv_timestamps) - 1

            actual_x = self.deriv_timestamps[idx]
            actual_y = self.deriv_readings[idx]

            self.deriv_crosshair_v.setPos(actual_x)
            self.deriv_crosshair_h.setPos(actual_y)
            self.deriv_crosshair_label.setPos(actual_x, actual_y)
            self.deriv_crosshair_label.setText(f"T: {actual_x:.2f}s\nΔ: {self._format_scientific_string(actual_y)}")

    def _toggle_sampling_state(self):
        if self.acquisition_thread and self.acquisition_thread.is_running:
            self.acquisition_thread.stop()
            self._enable_region_analysis()
        else:
            self._disable_region_analysis()
            if self.acquisition_thread:
                self.acquisition_thread.start()

    def _enable_region_analysis(self):
        if not self.timestamps: return
        t = LANGS.get(self.current_lang, LANGS["EN"])
        self.plot_stats_group.setTitle(t["grp_plot_stats_region"])
        view_range = self.plot_widget.viewRange()[0]
        self.region_selector.setRegion([view_range[0], view_range[1]])
        self.region_selector.show()
        self._calculate_region_statistics()

    def _disable_region_analysis(self):
        t = LANGS.get(self.current_lang, LANGS["EN"])
        self.plot_stats_group.setTitle(t["grp_plot_stats_global"])
        self.region_selector.hide()

        if self.timestamps:
            avg_val = self.plot_sum / len(self.readings)
            self._display_plot_statistics(self.plot_min, self.plot_max, avg_val, mode="GLOBAL")
            if len(self.timestamps) > 0 and self.plot_min != float('inf'):
                try:
                    self.min_marker.setData([self.timestamps[self.readings.index(self.plot_min)]], [self.plot_min])
                    self.max_marker.setData([self.timestamps[self.readings.index(self.plot_max)]], [self.plot_max])
                except ValueError: pass
        else:
            self._display_plot_statistics(float('inf'), float('-inf'), 0.0, mode="GLOBAL")

    def _calculate_region_statistics(self):
        if not self.timestamps or not self.region_selector.isVisible(): return
        region_start, region_end = self.region_selector.getRegion()

        start_idx = bisect.bisect_left(self.timestamps, region_start)
        end_idx = bisect.bisect_right(self.timestamps, region_end)

        if start_idx >= end_idx:
            self._display_plot_statistics(float('inf'), float('-inf'), 0.0, mode="REGION")
            self.min_marker.setData([], [])
            self.max_marker.setData([], [])
            return

        r_slice = self.readings[start_idx:end_idx]
        r_time = self.timestamps[start_idx:end_idx]

        r_min = min(r_slice)
        r_max = max(r_slice)
        r_avg = sum(r_slice) / len(r_slice)

        self.min_marker.setData([r_time[r_slice.index(r_min)]], [r_min])
        self.max_marker.setData([r_time[r_slice.index(r_max)]], [r_max])
        self._display_plot_statistics(r_min, r_max, r_avg, mode="REGION")

    def _display_plot_statistics(self, min_val: float, max_val: float, avg_val: float, mode: str):
        t = LANGS.get(self.current_lang, LANGS["EN"])
        if min_val == float('inf') or max_val == float('-inf'):
            self.lbl_plot_min.setText(f"{t['lbl_plot_min']} ---")
            self.lbl_plot_max.setText(f"{t['lbl_plot_max']} ---")
            self.lbl_plot_avg.setText(f"{t['lbl_plot_avg']} ---")
            return
        self.lbl_plot_min.setText(f"{t['lbl_plot_min']} {self._format_scientific_string(min_val)}")
        self.lbl_plot_max.setText(f"{t['lbl_plot_max']} {self._format_scientific_string(max_val)}")
        self.lbl_plot_avg.setText(f"{t['lbl_plot_avg']} {self._format_scientific_string(avg_val)}")

    def _initialize_new_plot_curve(self):
        import random
        self.timestamps.clear()
        self.readings.clear()
        self.deriv_timestamps.clear()
        self.deriv_readings.clear()

        self.plot_sum = 0.0
        self.plot_min = float('inf')
        self.plot_max = float('-inf')

        self.session_start_time = time.time()
        self.active_plot_curve = self.plot_widget.plot(pen=pg.mkPen(color=pg.hsvColor(random.random()), width=2))

        self.min_marker.setData([], [])
        self.max_marker.setData([], [])
        self.hist_curve.setData(x=np.array([0, 1]), y=np.array([0, 0]))
        self.deriv_curve.setData([], [])
        self._display_plot_statistics(float('inf'), float('-inf'), 0.0, mode="GLOBAL")

    def _reset_plot_data(self):
        self.plot_widget.clear()
        self.hist_widget.clear()
        self.deriv_widget.clear()

        self.timestamps.clear()
        self.readings.clear()
        self.deriv_timestamps.clear()
        self.deriv_readings.clear()

        self.plot_sum = 0.0
        self.plot_min = float('inf')
        self.plot_max = float('-inf')

        self.session_start_time = time.time()
        self._init_plot_elements()
        self._disable_region_analysis()

    def _update_y_axis_label(self):
        t = LANGS.get(self.current_lang, LANGS["EN"])
        mode_key = self.mode_selector.currentText()
        math_mode = self.math_selector.currentText()

        y_label = mode_key
        if math_mode == "DBM": y_label += " [dBm]"
        elif math_mode == "DB": y_label += " [dB]"
        elif math_mode == "NULL": y_label += " [REL]"

        self.plot_widget.setLabel('left', y_label)
        self.hist_widget.setLabel('bottom', y_label)
        self.hist_widget.setLabel('left', t["lbl_counts"])
        self.deriv_widget.setLabel('bottom', t["lbl_time"])
        self.deriv_widget.setLabel('left', f"Δ {y_label} / s")

    def _toggle_csv_logging(self):
        t = LANGS.get(self.current_lang, LANGS["EN"])
        if self.btn_log_toggle.isChecked():
            file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv);;All Files (*)")
            if file_path:
                try:
                    self.csv_file_handle = open(file_path, 'a', newline='', encoding='utf-8')
                    self.csv_writer = csv.writer(self.csv_file_handle)
                    self.csv_writer.writerow(["Timestamp", "Mode", "Value", "PF_Status"])
                    self.is_logging_active = True
                    self.btn_log_toggle.setText(t["btn_log_stop"])
                    self.btn_log_toggle.setProperty("btn_type", "danger")
                    self.btn_log_toggle.style().unpolish(self.btn_log_toggle)
                    self.btn_log_toggle.style().polish(self.btn_log_toggle)
                except IOError as e:
                    QMessageBox.warning(self, "File System Error", f"I/O Error:\n{e}")
                    self.btn_log_toggle.setChecked(False)
            else: self.btn_log_toggle.setChecked(False)
        else:
            self.is_logging_active = False
            if self.csv_file_handle:
                self.csv_file_handle.close()
                self.csv_file_handle = None
            self.btn_log_toggle.setText(t["btn_log_start"])
            self.btn_log_toggle.setProperty("btn_type", "")
            self.btn_log_toggle.style().unpolish(self.btn_log_toggle)
            self.btn_log_toggle.style().polish(self.btn_log_toggle)

    def _handle_csv_logging(self, primary_val: float, mode_name: str, pf_status: str):
        if not self.is_logging_active or not self.csv_writer: return
        current_time_abs = time.time()
        interval = self.log_interval_spin.value()

        if current_time_abs - self.last_log_timestamp >= interval:
            timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time_abs))
            self.csv_writer.writerow([timestamp_str, mode_name, primary_val, pf_status])
            self.csv_file_handle.flush()
            self.last_log_timestamp = current_time_abs

    def save_settings(self):
        settings = {
            "lang": self.current_lang, "baudrate": self.baud_selector.currentText(),
            "data_bits": self.data_bits_selector.currentText(), "parity": self.parity_selector.currentText(),
            "stop_bits": self.stop_bits_selector.currentText(), "mode_index": self.mode_selector.currentIndex(),
            "rate_index": self.rate_selector.currentIndex(), "math_index": self.math_selector.currentIndex(),
            "auto_range": self.chk_auto_range.isChecked(), "range_index": self.range_selector.currentIndex(),
            "beeper": self.chk_beeper.isChecked(), "dual_display": self.chk_dual_display.isChecked(),
            "scientific_fmt": self.chk_scientific.isChecked(), "cont_threshold": self.cont_threshold_spin.value(),
            "temp_unit_index": self.temp_unit_selector.currentIndex(), "temp_type_index": self.temp_type_selector.currentIndex(),
            "temp_show_index": self.temp_show_selector.currentIndex(), "db_ref_index": self.db_ref_selector.currentIndex(),
            "null_offset": self.null_offset_spin.value(), "log_interval": self.log_interval_spin.value(),
            "plot_timebase": self.timebase_spin.value(), "sampling_rate": self.sampling_rate_spin.value(),
            "max_points": self.max_points_spin.value(), "enable_limits": self.chk_enable_limits.isChecked(),
            "limit_max": self.limit_max_spin.value(), "limit_min": self.limit_min_spin.value()
        }
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f: json.dump(settings, f, indent=4)
        except IOError: pass

    def _load_saved_configuration(self):
        if not os.path.exists(SETTINGS_FILE): return
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: cfg = json.load(f)
            # Default fallback shifted to "EN"
            self.current_lang = cfg.get("lang", "EN")
            self.baud_selector.setCurrentText(cfg.get("baudrate", "115200"))
            self.data_bits_selector.setCurrentText(cfg.get("data_bits", "8"))
            self.parity_selector.setCurrentText(cfg.get("parity", "None"))
            self.stop_bits_selector.setCurrentText(cfg.get("stop_bits", "1"))
            self.mode_selector.blockSignals(True)
            self.mode_selector.setCurrentIndex(cfg.get("mode_index", 0))
            self.mode_selector.blockSignals(False)
            self.rate_selector.setCurrentIndex(cfg.get("rate_index", 0))
            self.math_selector.setCurrentIndex(cfg.get("math_index", 0))
            self.chk_auto_range.setChecked(cfg.get("auto_range", True))
            self.range_selector.setCurrentIndex(cfg.get("range_index", 0))
            self.chk_beeper.setChecked(cfg.get("beeper", True))
            self.chk_dual_display.setChecked(cfg.get("dual_display", False))
            self.chk_scientific.setChecked(cfg.get("scientific_fmt", False))
            self.cont_threshold_spin.setValue(cfg.get("cont_threshold", 50))
            self.temp_unit_selector.setCurrentIndex(cfg.get("temp_unit_index", 0))
            self.temp_type_selector.setCurrentIndex(cfg.get("temp_type_index", 0))
            self.temp_show_selector.setCurrentIndex(cfg.get("temp_show_index", 0))
            self.db_ref_selector.setCurrentIndex(cfg.get("db_ref_index", 0))
            self.null_offset_spin.setValue(cfg.get("null_offset", 0.0))
            self.log_interval_spin.setValue(cfg.get("log_interval", 1.0))
            self.timebase_spin.setValue(cfg.get("plot_timebase", 0))
            self.sampling_rate_spin.setValue(cfg.get("sampling_rate", 200))
            self.max_points_spin.setValue(cfg.get("max_points", 10000))
            self.chk_enable_limits.setChecked(cfg.get("enable_limits", False))
            self.limit_max_spin.setValue(cfg.get("limit_max", 5.0))
            self.limit_min_spin.setValue(cfg.get("limit_min", -5.0))
        except (IOError, json.JSONDecodeError): pass

        self._update_pf_region()

    def closeEvent(self, event):
        self.save_settings()
        self._terminate_connection()
        event.accept()

    def _apply_translations(self):
        t = LANGS.get(self.current_lang, LANGS["EN"])
        self.setWindowTitle(t["title"])
        self.tabs.setTabText(0, t["tab_conn"])
        self.tabs.setTabText(1, t["tab_meas"])
        self.tabs.setTabText(2, t["tab_adv"])

        self.btn_lang.setText(t["lang_switch"])
        self.conn_group.setTitle(t["grp_conn"])
        self.lbl_port.setText(t["lbl_port"])
        self.btn_refresh.setText(t["btn_refresh"])
        self.btn_connect.setText(t["btn_connect"])
        self.btn_disconnect.setText(t["btn_disconnect"])
        self.btn_reset.setText(t["btn_reset"])

        self.config_group.setTitle(t["grp_config"])
        self.lbl_mode.setText(t["lbl_mode"])
        self.lbl_rate.setText(t["lbl_rate"])
        self.lbl_math.setText(t["lbl_math"])
        self.chk_auto_range.setText(t["chk_auto_range"])
        self.lbl_range.setText(t["lbl_range"])
        self.chk_beeper.setText(t["chk_beeper"])
        self.chk_dual_display.setText(t["chk_dual_display"])
        self.chk_scientific.setText(t["chk_scientific"])

        self.pf_group.setTitle(t["grp_pass_fail"])
        self.chk_enable_limits.setText(t["chk_enable_limits"])
        self.lbl_upper_limit.setText(t["lbl_upper_limit"])
        self.lbl_lower_limit.setText(t["lbl_lower_limit"])

        self.adv_group.setTitle(t["grp_adv"])
        self.lbl_cont.setText(t["lbl_cont"])
        self.lbl_temp_unit.setText(t["lbl_temp_unit"])
        self.lbl_temp_sens.setText(t["lbl_temp_sens"])
        self.lbl_temp_show.setText(t["lbl_temp_show"])
        self.lbl_db_ref.setText(t["lbl_db_ref"])
        self.lbl_null_offset.setText(t["lbl_null_offset"])
        self.btn_apply_adv.setText(t["btn_apply_adv"])

        self.hw_group.setTitle(t["grp_hardware"])
        self.btn_get_stats.setText(t["btn_get_stats"])
        self.btn_get_rtc.setText(t["btn_get_rtc"])

        self.log_group.setTitle(t["grp_log"])
        self.lbl_interval.setText(t["lbl_interval"])
        self.btn_log_toggle.setText(t["btn_log_stop"] if self.is_logging_active else t["btn_log_start"])

        # Update information tooltips
        for icon_lbl, key in self.help_icons_list:
            icon_lbl.setToolTip(t[key])

        # Update plot titles in wrappers
        for title_lbl, key in self.plot_titles:
            title_lbl.setText(t[key])

        if hasattr(self, 'region_selector') and self.region_selector.isVisible():
            self.plot_stats_group.setTitle(t["grp_plot_stats_region"])
        else:
            self.plot_stats_group.setTitle(t["grp_plot_stats_global"])

        if not self.readings:
            self.lbl_plot_min.setText(f"{t['lbl_plot_min']} ---")
            self.lbl_plot_max.setText(f"{t['lbl_plot_max']} ---")
            self.lbl_plot_avg.setText(f"{t['lbl_plot_avg']} ---")

        self.lbl_timebase.setText(t["lbl_timebase"])
        self.lbl_sampling_rate.setText(t["lbl_sampling_rate"])
        self.lbl_max_points.setText(t["lbl_max_points"])

        self.btn_start_stop.setText(t["btn_pause"])
        self.btn_new_curve.setText(t["btn_new_curve"])
        self.btn_clear.setText(t["btn_clear"])

        self.plot_widget.setLabel('bottom', t["lbl_time"])
        self._update_y_axis_label()

        if not self.instrument:
            self.lbl_pf_indicator.setText(t["lbl_status_idle"])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(MODERN_STYLE)
    window = DiagnosticDashboard()
    window.resize(1300, 800)
    window.show()
    sys.exit(app.exec_())

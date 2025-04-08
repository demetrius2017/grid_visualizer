from PyQt5 import QtWidgets, QtGui
from graph import MarketGraph
from trading import TradingSimulator
import os

class GridSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Grid Settings")
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout()

        self.grid_size_label = QtWidgets.QLabel("Grid Step Percentage:")
        self.grid_size_input = QtWidgets.QLineEdit()
        self.grid_size_input.setValidator(QtGui.QDoubleValidator(0.01, 100.0, 2))
        layout.addWidget(self.grid_size_label)
        layout.addWidget(self.grid_size_input)

        self.volatility_label = QtWidgets.QLabel("Volatility:")
        self.volatility_input = QtWidgets.QLineEdit()
        self.volatility_input.setValidator(QtGui.QDoubleValidator(0.0001, 1.0, 3))
        layout.addWidget(self.volatility_label)
        layout.addWidget(self.volatility_input)

        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.clicked.connect(self.accept)
        layout.addWidget(self.apply_button)

        self.setLayout(layout)

    def get_settings(self):
        return {"grid_size": float(self.grid_size_input.text()), "volatility": float(self.volatility_input.text())}


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trading Simulator")
        self.setGeometry(100, 100, 1200, 800)

        self.graph = MarketGraph()
        self.setCentralWidget(self.graph)

        self.simulator = TradingSimulator(self.graph)

        self.init_menu()
        self.init_toolbar()
        self.show()

    def init_toolbar(self):
        toolbar = self.addToolBar("Controls")

        clear_action = QtWidgets.QAction("Clear", self)
        clear_action.triggered.connect(self.clear_simulation)
        toolbar.addAction(clear_action)

    def clear_simulation(self):
        self.simulator.clear()
        print("Simulation cleared")

    def init_menu(self):
        menubar = self.menuBar()
        grid_menu = menubar.addMenu("Grid")

        grid_settings_action = QtWidgets.QAction("Grid Settings", self)
        grid_settings_action.triggered.connect(self.open_grid_settings)
        grid_menu.addAction(grid_settings_action)

        initialize_grid_action = QtWidgets.QAction("Initialize Grid", self)
        initialize_grid_action.triggered.connect(self.simulator.initialize_grid)
        grid_menu.addAction(initialize_grid_action)

        start_simulation_action = QtWidgets.QAction("Start Simulation", self)
        start_simulation_action.triggered.connect(self.simulator.start)
        grid_menu.addAction(start_simulation_action)

        stop_simulation_action = QtWidgets.QAction("Stop Simulation", self)
        stop_simulation_action.triggered.connect(self.simulator.stop)
        grid_menu.addAction(stop_simulation_action)

        mode_menu = menubar.addMenu("Simulation Mode")

        # Random mode
        self.random_mode_action = QtWidgets.QAction("Random", self, checkable=True)
        self.random_mode_action.setChecked(True)
        self.random_mode_action.triggered.connect(lambda: self.set_simulation_mode("random"))
        mode_menu.addAction(self.random_mode_action)

        # File submenu
        self.file_mode_menu = mode_menu.addMenu("From CSV File")
        self.csv_file_actions = []
        self.populate_file_menu()

    def populate_file_menu(self):
        data_dir = os.path.join(os.getcwd(), "data")
        for filename in os.listdir(data_dir):
            if filename.endswith(".csv"):
                action = QtWidgets.QAction(filename, self, checkable=True)
                action.triggered.connect(lambda checked, f=filename: self.set_csv_file(f))
                self.file_mode_menu.addAction(action)
                self.csv_file_actions.append(action)

    def set_simulation_mode(self, mode):
        self.simulator.simulation_mode = mode
        self.random_mode_action.setChecked(mode == "random")
        for action in self.csv_file_actions:
            action.setChecked(False)

    def set_csv_file(self, filename):
        self.set_simulation_mode("file")
        for action in self.csv_file_actions:
            action.setChecked(action.text() == filename)
        filepath = os.path.join("data", filename)
        self.simulator.set_csv_file(filepath)

    def open_grid_settings(self):
        dialog = GridSettingsDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            settings = dialog.get_settings()
            self.simulator.set_grid_settings(settings)

    def closeEvent(self, event):
        # Закрываем окно позиций, если оно открыто
        if self.simulator.positions_window is not None:
            self.simulator.positions_window.close()
        event.accept()

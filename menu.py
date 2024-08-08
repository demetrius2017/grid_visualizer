from PyQt5 import QtWidgets
from graph import MarketGraph
from trading import TradingSimulator


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Trading Simulator")

        self.graph = MarketGraph()
        self.simulator = TradingSimulator(self.graph)

        self.initUI()

    def initUI(self):
        self.start_button = QtWidgets.QPushButton("Start Simulation", self)
        self.start_button.clicked.connect(self.simulator.start)

        self.stop_button = QtWidgets.QPushButton("Stop Simulation", self)
        self.stop_button.clicked.connect(self.simulator.stop)

        self.grid_settings_button = QtWidgets.QPushButton("Grid Settings", self)
        self.grid_settings_button.clicked.connect(self.show_grid_settings)

        self.init_grid_button = QtWidgets.QPushButton("Initialize Grid", self)
        self.init_grid_button.clicked.connect(self.initialize_grid)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.graph)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.grid_settings_button)
        layout.addWidget(self.init_grid_button)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def show_grid_settings(self):
        dialog = GridSettingsDialog(self.simulator)
        dialog.exec_()

    def initialize_grid(self):
        self.simulator.initialize_grid()


class GridSettingsDialog(QtWidgets.QDialog):
    def __init__(self, simulator):
        super().__init__()
        self.simulator = simulator
        self.setWindowTitle("Grid Settings")

        self.grid_size_input = QtWidgets.QDoubleSpinBox(self)
        self.grid_size_input.setDecimals(2)
        self.grid_size_input.setRange(0.01, 10.00)
        self.grid_size_input.setValue(self.simulator.grid_size)

        self.volatility_input = QtWidgets.QDoubleSpinBox(self)
        self.volatility_input.setDecimals(5)
        self.volatility_input.setRange(0.00001, 1.00000)
        self.volatility_input.setValue(self.simulator.volatility)

        layout = QtWidgets.QFormLayout()
        layout.addRow("Grid Size (%)", self.grid_size_input)
        layout.addRow("Volatility", self.volatility_input)

        self.button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.apply_settings)
        self.button_box.rejected.connect(self.reject)

        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def apply_settings(self):
        settings = {"grid_size": self.grid_size_input.value(), "volatility": self.volatility_input.value()}
        self.simulator.set_grid_settings(settings)
        self.accept()

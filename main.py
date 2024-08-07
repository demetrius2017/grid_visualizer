import sys
from PyQt5 import QtWidgets, QtCore
from graph import MarketGraph
from trading import TradingSimulator
from orders import OrderManager

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Market Trading Simulator")
        self.setGeometry(100, 100, 1200, 800)

        self.graph = MarketGraph()
        self.simulator = TradingSimulator(self.graph)

        self.setCentralWidget(self.graph)

        self.order_manager = self.simulator.order_manager

        self.initUI()

    def initUI(self):
        self.create_actions()
        self.create_menus()
        self.create_toolbar()

        self.statusBar().showMessage("Ready")

    def create_actions(self):
        self.buy_action = QtWidgets.QAction("&Buy", self)
        self.buy_action.triggered.connect(self.place_buy_order)

        self.sell_action = QtWidgets.QAction("&Sell", self)
        self.sell_action.triggered.connect(self.place_sell_order)

        self.start_action = QtWidgets.QAction("&Start", self)
        self.start_action.triggered.connect(self.start_simulation)

        self.stop_action = QtWidgets.QAction("&Stop", self)
        self.stop_action.triggered.connect(self.stop_simulation)

        self.grid_settings_action = QtWidgets.QAction("&Grid Settings", self)
        self.grid_settings_action.triggered.connect(self.show_grid_settings)

    def create_menus(self):
        menubar = self.menuBar()
        order_menu = menubar.addMenu("&Orders")
        order_menu.addAction(self.buy_action)
        order_menu.addAction(self.sell_action)

        simulation_menu = menubar.addMenu("&Simulation")
        simulation_menu.addAction(self.start_action)
        simulation_menu.addAction(self.stop_action)

        settings_menu = menubar.addMenu("&Settings")
        settings_menu.addAction(self.grid_settings_action)

    def create_toolbar(self):
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.addAction(self.start_action)
        toolbar.addAction(self.stop_action)
        toolbar.addAction(self.buy_action)
        toolbar.addAction(self.sell_action)
        toolbar.addAction(self.grid_settings_action)

    def place_buy_order(self):
        price = self.simulator.current_price
        volume = 1  # Задайте желаемый объем
        self.order_manager.place_order('buy', price, volume)
        self.statusBar().showMessage(f"Buy order placed at {price}")

    def place_sell_order(self):
        price = self.simulator.current_price
        volume = 1  # Задайте желаемый объем
        self.order_manager.place_order('sell', price, volume)
        self.statusBar().showMessage(f"Sell order placed at {price}")

    def start_simulation(self):
        self.simulator.start()
        self.statusBar().showMessage("Simulation started")

    def stop_simulation(self):
        self.simulator.stop()
        self.statusBar().showMessage("Simulation stopped")

    def show_grid_settings(self):
        grid_settings_dialog = GridSettingsDialog(self)
        if grid_settings_dialog.exec_():
            self.simulator.set_grid_settings(grid_settings_dialog.get_settings())

class GridSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Grid Settings")

        self.grid_size_label = QtWidgets.QLabel("Grid Size:", self)
        self.grid_size_input = QtWidgets.QSpinBox(self)
        self.grid_size_input.setRange(1, 100)

        self.volatility_label = QtWidgets.QLabel("Volatility:", self)
        self.volatility_input = QtWidgets.QDoubleSpinBox(self)
        self.volatility_input.setRange(0.001, 0.1)
        self.volatility_input.setSingleStep(0.001)

        self.layout = QtWidgets.QFormLayout()
        self.layout.addRow(self.grid_size_label, self.grid_size_input)
        self.layout.addRow(self.volatility_label, self.volatility_input)
        self.setLayout(self.layout)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addRow(self.buttons)

    def get_settings(self):
        return {
            'grid_size': self.grid_size_input.value(),
            'volatility': self.volatility_input.value()
        }

def main():
    app = QtWidgets.QApplication([])

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

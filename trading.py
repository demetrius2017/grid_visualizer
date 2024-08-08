import numpy as np
from PyQt5 import QtCore, QtGui
from orders import OrderManager

class TradingSimulator:
    def __init__(self, graph):
        self.graph = graph
        self.current_price = 0.5
        self.volatility = 0.005
        self.stop_simulation = True
        self.grid_size = 1.00  # Grid size in percentage
        self.order_manager = OrderManager(self.grid_size)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)

        self.graph.graphWidget.scene().sigMouseMoved.connect(self.mouse_moved)

    def start(self):
        self.stop_simulation = False
        self.timer.start(50)
        print("Simulation started")

    def stop(self):
        self.stop_simulation = True
        self.timer.stop()
        print("Simulation stopped")

    def set_grid_settings(self, settings):
        self.grid_size = settings['grid_size']
        self.volatility = settings['volatility']
        self.order_manager.grid_step_percent = self.grid_size
        print(f"Grid settings updated: grid_size={self.grid_size}, volatility={self.volatility}")

    def update(self):
        if not self.stop_simulation:
            new_price = max(0, self.current_price + np.random.uniform(-self.volatility, self.volatility))
            print(f"New price: {new_price}")
            self.graph.update_graph(new_price)
            self.order_manager.check_orders(new_price)
            self.current_price = new_price

    def mouse_moved(self, evt):
        pos = evt
        if self.graph.graphWidget.sceneBoundingRect().contains(pos):
            mouse_point = self.graph.graphWidget.plotItem.vb.mapSceneToView(pos)
            cursor_position = mouse_point.y()
            modifiers = QtGui.QGuiApplication.keyboardModifiers()
            if modifiers == QtCore.Qt.ShiftModifier:
                self.current_price = max(0, cursor_position + np.random.uniform(-self.volatility, self.volatility))
                print(f"Mouse moved: new current price={self.current_price}")

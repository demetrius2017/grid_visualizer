import numpy as np
from PyQt5 import QtCore, QtGui
from orders import OrderManager

class TradingSimulator:
    def __init__(self, graph):
        self.graph = graph
        self.order_manager = OrderManager()
        self.current_price = 0.5
        self.volatility = 0.005
        self.stop_simulation = True
        self.grid_size = 10

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)

        self.graph.graphWidget.scene().sigMouseMoved.connect(self.mouse_moved)
        self.graph.graphWidget.scene().sigMouseClicked.connect(self.mouse_clicked)

    def start(self):
        self.stop_simulation = False
        self.timer.start(50)

    def stop(self):
        self.stop_simulation = True
        self.timer.stop()

    def set_grid_settings(self, settings):
        self.grid_size = settings['grid_size']
        self.volatility = settings['volatility']

    def update(self):
        if not self.stop_simulation:
            new_price = max(0, self.current_price + np.random.uniform(-self.volatility, self.volatility))
            self.graph.update_graph(new_price)
            self.order_manager.check_orders(new_price)
            self.current_price = new_price

    def mouse_moved(self, evt):
        pos = evt
        if self.graph.graphWidget.sceneBoundingRect().contains(pos):
            mouse_point = self.graph.graphWidget.plotItem.vb.mapSceneToView(pos)
            cursor_position = mouse_point.y()
            if QtGui.QGuiApplication.mouseButtons() == QtCore.Qt.LeftButton:
                self.current_price = max(0, cursor_position + np.random.uniform(-self.volatility, self.volatility))

    def mouse_clicked(self, evt):
        if evt.button() == QtCore.Qt.LeftButton:
            self.current_price = max(0, evt.scenePos().y())


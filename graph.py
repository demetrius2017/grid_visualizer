from PyQt5 import QtWidgets
import pyqtgraph as pg


class MarketGraph(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Market Price Simulation")
        self.setGeometry(100, 100, 1000, 600)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.graphWidget = pg.PlotWidget()
        layout.addWidget(self.graphWidget)

        self.curve = self.graphWidget.plot(pen="y")
        self.graphWidget.setYRange(0, 1)
        self.graphWidget.showGrid(x=True, y=True)

        self.data = []

    def update_graph(self, new_price):
        self.data.append(new_price)
        if len(self.data) > 100:
            self.data.pop(0)
        self.curve.setData(self.data)

    def update_orders(self, orders):
        self.graphWidget.clear()
        self.curve = self.graphWidget.plot(self.data, pen="y")
        for order in orders:
            if not order.executed:
                color = "g" if order.order_type == "buy" else "r"
                line = pg.InfiniteLine(pos=order.price, angle=0, pen=color)
                self.graphWidget.addItem(line)

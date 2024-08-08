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
        self.ema_curve = self.graphWidget.plot(pen="b")  # EMA line
        self.graphWidget.setYRange(0, 1)
        self.graphWidget.showGrid(x=True, y=True)

        self.data = []
        self.ema_data = []
        self.order_history = []

    def update_graph(self, new_price):
        self.data.append(new_price)
        if len(self.data) > 100:
            self.data.pop(0)
        self.curve.setData(self.data)

    def update_ema(self, ema):
        self.ema_data = ema
        if len(self.ema_data) > 100:
            self.ema_data = self.ema_data[-100:]
        self.ema_curve.setData(self.ema_data)

    def update_orders(self, orders):
        self.graphWidget.clear()
        self.curve = self.graphWidget.plot(self.data, pen="y")
        self.ema_curve = self.graphWidget.plot(self.ema_data, pen="b")
        for order in orders:
            if not order.executed:
                color = "g" if order.order_type == "buy" else "r"
                line = pg.InfiniteLine(pos=order.price, angle=0, pen=pg.mkPen(color=color, style=pg.QtCore.Qt.DashLine))
                self.graphWidget.addItem(line)
        for order in self.order_history:
            color = pg.mkColor(100, 100, 100, 50)  # Бледно-серый цвет
            self.graphWidget.plot([order.price], pen=pg.mkPen(color=color), symbol="o", symbolPen=color)

    def add_order_to_history(self, order):
        self.order_history.append(order)

from PyQt5 import QtWidgets
import pyqtgraph as pg

class MarketGraph(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QtWidgets.QVBoxLayout(self)
        self.graphWidget = pg.PlotWidget()
        self.layout.addWidget(self.graphWidget)

        self.report_label = QtWidgets.QLabel()
        self.layout.addWidget(self.report_label)

        self.balance_graph = pg.PlotWidget()
        self.layout.addWidget(self.balance_graph)

        self.init_graph()

    def init_graph(self):
        self.graphWidget.setTitle("Market Price Simulation")
        self.graphWidget.setLabel('left', 'Price')
        self.graphWidget.setLabel('bottom', 'Time')
        self.graphWidget.showGrid(x=True, y=True)

        self.price_curve = self.graphWidget.plot(pen=pg.mkPen('y', width=1))
        self.ema_curve = self.graphWidget.plot(pen=pg.mkPen('b', width=1))
        self.buy_orders_curve = self.graphWidget.plot(pen=pg.mkPen('g', width=1, style=pg.QtCore.Qt.DotLine))
        self.sell_orders_curve = self.graphWidget.plot(pen=pg.mkPen('r', width=1, style=pg.QtCore.Qt.DotLine))

        self.balance_graph.setTitle("Balance, Free Margin, and Margin")
        self.balance_graph.setLabel('left', 'Value')
        self.balance_graph.setLabel('bottom', 'Time')
        self.balance_graph.showGrid(x=True, y=True)

        self.balance_curve = self.balance_graph.plot(pen=pg.mkPen('g', width=1), name="Balance")
        self.free_margin_curve = self.balance_graph.plot(pen=pg.mkPen('b', width=1), name="Free Margin")
        self.margin_curve = self.balance_graph.plot(pen=pg.mkPen('r', width=1), name="Margin")

    def update_graph(self, price_data):
        self.price_curve.setData(price_data)

    def update_ema(self, ema_data):
        self.ema_curve.setData(ema_data)

    def update_orders(self, buy_orders, sell_orders):
        self.buy_orders_curve.setData(buy_orders)
        self.sell_orders_curve.setData(sell_orders)

    def update_report(self, balance, profit, floating_profit, free_margin):
        self.report_label.setText(f"Balance: {balance}, Profit: {profit}, Floating Profit: {floating_profit}, Free Margin: {free_margin}")

    def update_balance_graph(self, balance_history, free_margin_history, margin_history):
        self.balance_curve.setData(balance_history)
        self.free_margin_curve.setData(free_margin_history)
        self.margin_curve.setData(margin_history)

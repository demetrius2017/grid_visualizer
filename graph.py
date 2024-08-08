from PyQt5 import QtWidgets, QtGui, QtCore
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

        self.orders_table = QtWidgets.QTableWidget()
        self.orders_table.setColumnCount(6)
        self.orders_table.setHorizontalHeaderLabels(["ID", "Price", "Direction", "Commission", "Volume", "Profit"])
        self.layout.addWidget(self.orders_table)

        self.init_graph()

    def init_graph(self):
        self.graphWidget.setTitle("Market Price Simulation")
        self.graphWidget.setLabel('left', 'Price')
        self.graphWidget.setLabel('bottom', 'Time')
        self.graphWidget.showGrid(x=True, y=True)

        self.price_curve = self.graphWidget.plot(pen=pg.mkPen('y', width=1))
        self.ema_curve = self.graphWidget.plot(pen=pg.mkPen('b', width=1))
        self.buy_orders_curve = pg.ScatterPlotItem(pen=pg.mkPen('g'), brush=pg.mkBrush(0, 255, 0, 120), size=10)
        self.sell_orders_curve = pg.ScatterPlotItem(pen=pg.mkPen('r'), brush=pg.mkBrush(255, 0, 0, 120), size=10)
        self.graphWidget.addItem(self.buy_orders_curve)
        self.graphWidget.addItem(self.sell_orders_curve)

        self.balance_graph.setTitle("Balance, Free Margin, and Margin")
        self.balance_graph.setLabel('left', 'Value')
        self.balance_graph.setLabel('bottom', 'Time')
        self.balance_graph.showGrid(x=True, y=True)

        self.balance_curve = self.balance_graph.plot(pen=pg.mkPen('g', width=1), name="Balance")
        self.free_margin_curve = self.balance_graph.plot(pen=pg.mkPen('b', width=1), name="Free Margin")
        self.margin_curve = self.balance_graph.plot(pen=pg.mkPen('r', width=1), name="Margin")

    def update_graph(self, price_data):
        self.price_curve.setData(range(len(price_data)), price_data)

    def update_ema(self, ema_data):
        self.ema_curve.setData(range(len(ema_data)), ema_data)

    def update_orders(self, buy_orders, sell_orders):
        buy_spots = [{'pos': (len(self.price_curve.getData()[0]) - 1, price), 'data': 1} for price in buy_orders]
        sell_spots = [{'pos': (len(self.price_curve.getData()[0]) - 1, price), 'data': 1} for price in sell_orders]
        self.buy_orders_curve.setData(buy_spots)
        self.sell_orders_curve.setData(sell_spots)

    def update_report(self, balance, profit, floating_profit, free_margin):
        self.report_label.setText(f"Balance: {balance}, Profit: {profit}, Floating Profit: {floating_profit}, Free Margin: {free_margin}")

    def update_balance_graph(self, balance_history, free_margin_history, margin_history):
        self.balance_curve.setData(range(len(balance_history)), balance_history)
        self.free_margin_curve.setData(range(len(free_margin_history)), free_margin_history)
        self.margin_curve.setData(range(len(margin_history)), margin_history)

    def update_order_history(self, order_history):
        self.orders_table.setRowCount(len(order_history))
        for i, order in enumerate(order_history):
            self.orders_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(i)))
            self.orders_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{order.price:.2f}"))
            self.orders_table.setItem(i, 2, QtWidgets.QTableWidgetItem(order.order_type))
            self.orders_table.setItem(i, 3, QtWidgets.QTableWidgetItem("0"))  # Assuming no commission
            self.orders_table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{order.volume:.2f}"))
            self.orders_table.setItem(i, 5, QtWidgets.QTableWidgetItem(f"{self.calculate_order_profit(order):.2f}"))

    def calculate_order_profit(self, order):
        if order.executed:
            return (order.volume * (order.execution_price - order.price) if order.order_type == 'buy' else order.volume * (order.price - order.execution_price))
        return 0.0

import numpy as np
from PyQt5 import QtCore, QtGui
from orders import OrderManager

class TradingSimulator:
    def __init__(self, graph, ema_period=20):
        self.graph = graph
        self.current_price = 0.5
        self.volatility = 0.005  # Устанавливаем значение по умолчанию
        self.stop_simulation = True
        self.grid_size = 1.00  # Grid size in percentage
        self.order_manager = OrderManager(self.grid_size)
        self.ema_period = ema_period
        self.prices = []  # To store historical prices
        self.ema = []  # To store EMA values
        self.balance_history = []
        self.free_margin_history = []
        self.margin_history = []

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
        self.order_manager.volatility = self.volatility
        print(f"Grid settings updated: grid_size={self.grid_size}, volatility={self.volatility}")

    def update(self):
        if not self.stop_simulation:
            new_price = max(0, self.current_price + np.random.uniform(-self.volatility, self.volatility))
            self.prices.append(new_price)
            if len(self.prices) >= self.ema_period:
                if len(self.ema) == 0:
                    self.ema.append(np.mean(self.prices[-self.ema_period:]))
                else:
                    k = 2 / (self.ema_period + 1)
                    new_ema = new_price * k + self.ema[-1] * (1 - k)
                    self.ema.append(new_ema)

                # Update graph and orders after EMA is calculated
                self.graph.update_graph(self.prices)  # Передаем список цен
                self.graph.update_ema(self.ema)
                self.order_manager.check_orders(new_price)
                self.current_price = new_price

                # Initialize grid if not already done and sufficient data is available
                if not self.order_manager.orders:
                    self.initialize_grid()
                else:
                    self.order_manager.update_grid(self.ema, 10, 1)

                self.update_report()
            else:
                self.graph.update_graph(self.prices)  # Передаем список цен
                self.current_price = new_price

    def initialize_grid(self):
        if len(self.ema) > 0:
            base_price = self.ema[-1]
            num_orders = 10  # Количество ордеров в каждом направлении
            volume = 1  # Объем каждого ордера
            self.order_manager.initialize_grid(self.ema, num_orders, volume)

    def update_report(self):
        balance = self.order_manager.get_balance()
        profit = self.order_manager.get_profit()
        floating_profit = self.order_manager.get_floating_profit()
        free_margin = self.order_manager.get_free_margin()

        self.balance_history.append(balance)
        self.free_margin_history.append(free_margin)
        self.margin_history.append(balance - free_margin)

        self.graph.update_report(balance, profit, floating_profit, free_margin)
        self.graph.update_balance_graph(self.balance_history, self.free_margin_history, self.margin_history)
        self.update_orders_graph()
        self.graph.update_order_history(self.order_manager.get_order_history())
        print(f"Balance: {balance}, Profit: {profit}, Floating Profit: {floating_profit}, Free Margin: {free_margin}")

    def update_orders_graph(self):
        buy_orders = [order.price for order in self.order_manager.orders if order.order_type == 'buy' and not order.executed]
        sell_orders = [order.price for order in self.order_manager.orders if order.order_type == 'sell' and not order.executed]
        self.graph.update_orders(buy_orders, sell_orders)


    def mouse_moved(self, evt):
        pos = evt
        if self.graph.graphWidget.sceneBoundingRect().contains(pos):
            mouse_point = self.graph.graphWidget.plotItem.vb.mapSceneToView(pos)
            cursor_position = mouse_point.y()
            modifiers = QtGui.QGuiApplication.keyboardModifiers()
            if modifiers == QtCore.Qt.ShiftModifier:
                self.current_price = max(0, cursor_position + np.random.uniform(-self.volatility, self.volatility))
                print(f"Mouse moved: new current price={self.current_price}")

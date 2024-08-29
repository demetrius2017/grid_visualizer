import numpy as np
from PyQt5 import QtCore, QtGui
from orders import OrderManager
from positions_window import PositionsWindow


class TradingSimulator:
    def __init__(
        self,
        graph,
        initial_balance=10000,
        commission_rate=0.16/100,
        grid_size=10,
        ema_period=20,
        min_grid_coverage=0.05,
        min_orders=2,
        max_orders=6,
    ):
        self.graph = graph
        self.current_price = 0.5
        self.volatility = 0.005  # Устанавливаем значение по умолчанию
        self.stop_simulation = True
        self.grid_size = grid_size
        self.order_manager = OrderManager(
            initial_balance,
            commission_rate,
            grid_size,
            graph,
            min_grid_coverage=min_grid_coverage,
            min_orders=min_orders,
            max_orders=max_orders,
        )
        self.ema_period = ema_period
        self.prices = []  # To store historical prices
        self.ema = []  # To store EMA values
        self.balance_history = []
        self.free_margin_history = []
        self.margin_history = []
        self.positions_window = None

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.update_counter = 0
        self.update_frequency = 1  # Обновлять график каждые 10 итераций
        self.price_buffer = []  # Буфер для хранения промежуточных цен

        self.graph.graphWidget.scene().sigMouseMoved.connect(self.mouse_moved)

    def start(self):
        self.stop_simulation = False
        self.initialize_grid()  # Добавьте эту строку
        self.timer.start(50)
        print("Simulation started")

    def stop(self):
        self.stop_simulation = True
        self.timer.stop()
        print("Simulation stopped")

    def set_grid_settings(self, settings):
        self.grid_size = settings["grid_size"]
        self.volatility = settings["volatility"]
        self.order_manager.grid_step_percent = self.grid_size
        self.order_manager.volatility = self.volatility
        print(f"Grid settings updated: grid_size={self.grid_size}, volatility={self.volatility}")

    def update(self):
        new_price = max(0, self.current_price + np.random.uniform(-self.volatility, self.volatility))
        self.price_buffer.append(new_price)
        self.current_price = new_price

        if len(self.price_buffer) >= self.update_frequency:
            self.prices.extend(self.price_buffer)
            self.price_buffer = []

            if len(self.ema) > len(self.prices):
                self.ema = self.ema[-len(self.prices):]

            while len(self.ema) < len(self.prices):
                if len(self.ema) == 0:
                    self.ema.append(np.mean(self.prices[-self.ema_period:]))
                else:
                    k = 2 / (self.ema_period + 1)
                    new_ema = self.prices[len(self.ema)] * k + self.ema[-1] * (1 - k)
                    self.ema.append(new_ema)

            self.order_manager.current_ema = self.ema[-1]
            self.order_manager.current_price = new_price
            self.order_manager.price_history = self.prices

            # Проверка и исполнение ордеров
            self.order_manager.check_orders(new_price)

            self.update_display()

    def update_display(self):
        buy_orders = [order for order in self.order_manager.orders if order.order_type == "buy" and not order.executed]
        sell_orders = [order for order in self.order_manager.orders if order.order_type == "sell" and not order.executed]
        distribution_data = self.order_manager.get_price_distribution_data()
        self.graph.set_full_data(self.prices, self.ema, buy_orders, sell_orders, self.order_manager.order_history, distribution_data)

        # Обновление таблицы исполненных ордеров и отчетов
        executed_orders = [order for order in self.order_manager.get_order_history() if order.executed]
        self.graph.update_orders_table(executed_orders)

        self.update_balances()
        self.update_report()
        self.update_positions_window()

    def update_positions_window(self):
        if self.positions_window is None:
            self.positions_window = PositionsWindow()
            self.positions_window.show()

        open_positions = self.order_manager.get_open_positions()
        closed_positions = self.order_manager.get_closed_positions()
        self.positions_window.update_positions(open_positions, closed_positions, self.current_price)

    def update_balances(self):
        self.balance_history.append(self.order_manager.get_balance())
        self.free_margin_history.append(self.order_manager.get_free_margin())
        self.margin_history.append(self.order_manager.get_balance() - self.order_manager.get_free_margin())
        if self.balance_history:  # Проверяем, есть ли вообще какие-либо данные
            self.graph.update_balance_graph(self.balance_history, self.free_margin_history, self.margin_history)

    def initialize_grid(self):
        if len(self.ema) > 0:
            print(f"Initializing grid with EMA: {self.ema[-1]}, Current Price: {self.current_price}")
            self.order_manager.update_grid(self.ema[-1], self.current_price, self.prices)
        else:
            print("Cannot initialize grid: EMA not yet calculated")

    def update_report(self):
        balance = self.order_manager.get_balance()
        profit = self.order_manager.get_profit()
        floating_profit = self.order_manager.get_floating_profit()
        free_margin = self.order_manager.get_free_margin()

        self.graph.update_report(balance, profit, floating_profit, free_margin)
        self.graph.update_order_history(self.order_manager.get_order_history())
        # print(f"Balance: {balance}, Profit: {profit}, Floating Profit: {floating_profit}, Free Margin: {free_margin}")

        # Проверка на критические уровни
        if free_margin < balance * 0.1:  # Если свободная маржа меньше 10% от баланса
            print("WARNING: Low free margin!")
        if floating_profit < -balance * 0.05:  # Если плавающий убыток больше 5% от баланса
            print("WARNING: High floating loss!")

    def update_orders_graph(self):
        buy_orders = [
            order.price for order in self.order_manager.orders if order.order_type == "buy" and not order.executed
        ]
        sell_orders = [
            order.price for order in self.order_manager.orders if order.order_type == "sell" and not order.executed
        ]
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

    def clear(self):
        self.current_price = 0.5  # или другое начальное значение
        self.prices = []
        self.ema = []
        self.balance_history = []
        self.free_margin_history = []
        self.margin_history = []
        self.order_manager.clear_orders()
        self.graph.clear_graph()
        print("Simulation cleared and reset")
        if self.positions_window:
            self.positions_window.clear()

    def update_orders_display(self):
        self.graph.update_orders(self.order_manager.orders)

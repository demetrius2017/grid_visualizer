import numpy as np
from PyQt5 import QtCore, QtGui
from orders import OrderManager
from positions_window import PositionsWindow


class TradingSimulator:
    def __init__(
        self,
        graph,
        initial_balance=10000,
        commission_rate=0.16 / 100,
        grid_size=10,
        ema_period=20,
        min_grid_coverage=0.3,
        min_orders=20,
        max_orders=50,
    ):
        self.graph = graph
        self.current_price = 0.5  # Устанавливаем начальную цену
        self.volatility = 0.005
        self.stop_simulation = True
        self.grid_size = grid_size
        self.ema_period = ema_period
        self.prices = [0.5]  # Инициализируем с начальной ценой
        self.ema = []
        self.balance_history = []
        self.free_margin_history = []
        self.margin_history = []
        self.positions_window = None

        # Создаем OrderManager с начальными данными
        self.order_manager = OrderManager(
            initial_balance,
            commission_rate,
            grid_size,
            graph,
            min_grid_coverage=min_grid_coverage,
            min_orders=min_orders,
            max_orders=max_orders,
        )

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.update_counter = 0
        self.update_frequency = 1
        self.price_buffer = []

        self.graph.graphWidget.scene().sigMouseMoved.connect(self.mouse_moved)

    def start(self):
        """Запуск симуляции с предварительной инициализацией EMA"""
        self.stop_simulation = False

        # Генерация начальных данных для EMA
        print(f"Generating initial data for EMA calculation (period={self.ema_period})")
        while len(self.prices) < self.ema_period:
            new_price = max(0, self.current_price + np.random.uniform(-self.volatility, self.volatility))
            self.prices.append(new_price)
            self.current_price = new_price
            print(f"Generated price: {new_price}")

        # Рассчитываем начальное значение EMA
        initial_ema = np.mean(self.prices[-self.ema_period :])
        self.ema.append(initial_ema)
        print(f"Initial EMA calculated: {initial_ema}")

        # Обновляем данные в OrderManager
        self.order_manager.current_ema = initial_ema
        self.order_manager.current_price = self.current_price
        self.order_manager.price_history = self.prices.copy()

        # Инициализируем сетку
        print("Initializing grid...")
        self.order_manager.initialize_grid()

        # Запускаем таймер обновления
        self.timer.start(50)
        print("Simulation started")

    def update(self):
        """Обновление состояния симуляции"""
        # Генерируем новую цену
        new_price = max(0, self.current_price + np.random.uniform(-self.volatility, self.volatility))
        self.price_buffer.append(new_price)
        self.current_price = new_price

        if len(self.price_buffer) >= self.update_frequency:
            # Добавляем новые цены в историю
            self.prices.extend(self.price_buffer)
            self.price_buffer = []

            # Обновляем EMA
            while len(self.ema) < len(self.prices):
                k = 2 / (self.ema_period + 1)
                if len(self.ema) == 0:
                    self.ema.append(np.mean(self.prices[-self.ema_period :]))
                else:
                    new_ema = self.prices[len(self.ema)] * k + self.ema[-1] * (1 - k)
                    self.ema.append(new_ema)

            # Обновляем данные в OrderManager
            self.order_manager.current_ema = self.ema[-1]
            self.order_manager.current_price = new_price
            self.order_manager.price_history = self.prices

            # Проверяем и исполняем ордера
            self.order_manager.check_orders(new_price)
            self.update_display()

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

    def update_display(self):
        buy_orders = [order for order in self.order_manager.orders if order.order_type == "buy" and not order.executed]
        sell_orders = [
            order for order in self.order_manager.orders if order.order_type == "sell" and not order.executed
        ]
        distribution_data = self.order_manager.get_price_distribution_data()

        self.graph.set_full_data(
            self.prices,
            self.ema,
            buy_orders,
            sell_orders,
            self.order_manager.order_history,
            distribution_data,
        )

        # # Обновляем информацию о хедже
        # self.graph.update_hedge_info(
        #     self.order_manager.options_manager.active_options, self.current_price
        # )

        executed_orders = [order for order in self.order_manager.get_order_history() if order.executed]
        self.graph.update_orders_table(executed_orders)

        self.update_balances()
        self.update_report()
        self.update_positions_window()

    def update_report(self):
        balance = self.order_manager.get_balance()
        total_profit = self.order_manager.get_total_profit()
        floating_profit = self.order_manager.get_floating_profit()
        free_margin = self.order_manager.get_free_margin()
        total_commission = self.order_manager.get_total_commission()
        hedge_metrics = self.order_manager.get_hedge_metrics()  # Получаем метрики хеджирования
        net_profit = total_profit - total_commission

        self.graph.update_report(
            balance,
            net_profit,
            floating_profit,
            free_margin,
            total_commission,
            hedge_metrics,  # Добавляем метрики хеджирования
        )
        self.graph.update_order_history(self.order_manager.get_order_history())

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

    def update_orders_graph(self):
        buy_orders = [
            order.price for order in self.order_manager.orders if order.order_type == "buy" and not order.executed
        ]
        sell_orders = [
            order.price for order in self.order_manager.orders if order.order_type == "sell" and not order.executed
        ]
        self.graph.update_orders(buy_orders, sell_orders)

    def update_positions_window(self):
        if self.positions_window is None:
            self.positions_window = PositionsWindow()
            self.positions_window.show()

        open_positions = self.order_manager.get_open_positions()
        closed_positions = self.order_manager.get_closed_positions()
        active_options = self.order_manager.options_manager.active_options
        options_history = self.order_manager.options_manager.options_history

        self.positions_window.update_positions(
            open_positions,
            closed_positions,
            self.current_price,
            active_options,
            options_history,
        )

    def mouse_moved(self, evt):
        pos = evt
        if self.graph.graphWidget.sceneBoundingRect().contains(pos):
            mouse_point = self.graph.graphWidget.plotItem.vb.mapSceneToView(pos)
            cursor_position = mouse_point.y()
            modifiers = QtGui.QGuiApplication.keyboardModifiers()
            if modifiers == QtCore.Qt.ShiftModifier:
                self.current_price = max(
                    0,
                    cursor_position + np.random.uniform(-self.volatility, self.volatility),
                )
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

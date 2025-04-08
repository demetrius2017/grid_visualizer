import numpy as np
from PyQt5 import QtCore, QtGui
from orders import OrderManager
from positions_window import PositionsWindow
import logging


class TradingSimulator:
    def __init__(
        self,
        graph,
        initial_balance=100000,
        grid_size=20,
        ema_period=50,
        min_grid_coverage=0.10,
        min_orders=5,
        max_orders=20,
    ):
        self.graph = graph
        self.volatility = 0.005
        self.stop_simulation = True
        self.grid_size = grid_size
        self.grid_step_percent = min_grid_coverage * 100 / grid_size
        self.ema_period = ema_period
        self.prices = [0.5]  # Инициализируем с начальной ценой
        self.ema = []
        self.balance_history = []
        self.free_margin_history = []
        self.margin_history = []
        self.positions_window = None
        self.simulation_mode = "random"
        self.file_prices = []
        self.file_index = 0
        self.csv_filepath = None
        self.performance_mode = True  # Флаг для отключения лишних обновлений
        self.max_history_size = 10000  # Максимальный размер истории для ограничения использования памяти
        self.gui_update_interval = 100  # Обновлять UI каждые 100 тиков
        if self.simulation_mode == "file" and self.file_prices:
            self.current_price = self.file_prices[0]  # Устанавливаем начальную цену из файла
        else:
            self.current_price = 0.5  # Устанавливаем начальную цену по умолчанию

        # Создаем OrderManager с начальными данными
        self.order_manager = OrderManager(
            initial_balance,
            self.grid_size,
            graph,
            self.grid_step_percent,
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

        # Создаем отдельный таймер для обновления окна позиций
        self.positions_timer = QtCore.QTimer()
        self.positions_timer.setInterval(500)  # Обновление каждые 500 мс
        self.positions_timer.timeout.connect(self.update_positions_window)

    def start(self):
        """Запуск симуляции с предварительной инициализацией EMA"""
        self.stop_simulation = False

        # Генерация начальных данных для EMA
        print(f"Generating initial data for EMA calculation (period={self.ema_period})")
        if self.simulation_mode == "file" and self.file_prices:
            self.prices = [price for _, price, _ in self.file_prices[:self.ema_period]]
            self.current_price = self.prices[-1]
        else:
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
        self.positions_timer.start()  # Запускаем таймер для обновления окна позиций
        print("Simulation started")

    def set_csv_file(self, filepath):
        self.csv_filepath = filepath
        self.simulation_mode = "file"
        self.load_price_history_from_csv(filepath)

    def load_price_history_from_csv(self, filepath):
        try:
            import csv
            from collections import defaultdict
            
            # Используем более эффективный CSV-парсер вместо ручного разбора
            csv_data = defaultdict(list)
            
            with open(filepath, 'r') as f:
                csv_reader = csv.reader(f)
                header = next(csv_reader, None)  # Пропускаем заголовок
                
                # Пакетная обработка данных для ускорения
                for row in csv_reader:
                    if len(row) >= 3:
                        timestamp, price_str, source = row[0], row[1], row[2]
                        try:
                            price = float(price_str)
                            csv_data[timestamp].append((price, source))
                        except (ValueError, IndexError):
                            continue
            
            # Конвертируем данные в нужный формат и сортируем
            self.file_prices = []
            for timestamp in sorted(csv_data.keys()):
                for price, source in csv_data[timestamp]:
                    self.file_prices.append((timestamp, price, source))
                    
            self.file_index = 0
            print(f"Loaded {len(self.file_prices)} prices from '{filepath}'")
        except Exception as e:
            print(f"Error loading CSV file: {e}")

    def update(self):
        """Обновление состояния симуляции с пакетной обработкой для ускорения"""
        self.update_counter += 1
        batch_size = 50  # Обрабатываем больше тиков за раз для реального ускорения

        if self.simulation_mode == "file":
            # Пакетная обработка для ускорения
            batch_processed = 0
            timestamps_batch = []
            prices_batch = []
            
            while batch_processed < batch_size and self.file_index < len(self.file_prices):
                timestamp, new_price, source = self.file_prices[self.file_index]
                self.file_index += 1
                batch_processed += 1
                
                # Собираем данные
                timestamps_batch.append(timestamp)
                prices_batch.append(new_price)
                
                # Устанавливаем текущую цену равной последней цене в пакете
                self.current_price = new_price
            
            # Если обработали хотя бы 1 тик
            if batch_processed > 0:
                # Добавляем все цены в историю
                self.prices.extend(prices_batch)
                
                # Ограничиваем размер истории
                if len(self.prices) > self.max_history_size:
                    self.prices = self.prices[-self.max_history_size:]
                
                # Обновляем EMA только для последней цены (оптимизация)
                k = 2 / (self.ema_period + 1)
                if len(self.ema) == 0:
                    self.ema.append(np.mean(self.prices[-self.ema_period:]))
                else:
                    new_ema = self.current_price * k + self.ema[-1] * (1 - k)
                    self.ema.append(new_ema)
                
                # Ограничиваем размер EMA
                if len(self.ema) > self.max_history_size:
                    self.ema = self.ema[-self.max_history_size:]
                
                # Обновляем данные в OrderManager
                self.order_manager.current_ema = self.ema[-1]
                self.order_manager.current_price = self.current_price
                self.order_manager.price_history = self.prices
                
                # Проверяем ордера ТОЛЬКО после обработки всего пакета
                self.order_manager.check_orders(self.current_price)
                
                # Обновляем UI независимо от счетчика при небольшом количестве тиков
                # и с интервалом при большем количестве для баланса скорости/отзывчивости
                if len(self.prices) < 1000 or self.update_counter % 5 == 0:
                    self.update_display()
                    
                # Обновляем баланс
                if self.update_counter % 10 == 0:
                    self.update_balances()
            
            # Если достигли конца файла
            if self.file_index >= len(self.file_prices):
                self.stop()
                return
        else:
            # Аналогичная пакетная обработка для режима random
            for _ in range(batch_size):
                new_price = max(0, self.current_price + np.random.uniform(-self.volatility, self.volatility))
                self.prices.append(new_price)
                self.current_price = new_price
                
            # Ограничиваем размер истории
            if len(self.prices) > self.max_history_size:
                self.prices = self.prices[-self.max_history_size:]
                
            # Обновляем EMA
            k = 2 / (self.ema_period + 1)
            if len(self.ema) == 0:
                self.ema.append(np.mean(self.prices[-self.ema_period:]))
            else:
                new_ema = self.current_price * k + self.ema[-1] * (1 - k)
                self.ema.append(new_ema)
                
            # Ограничиваем размер EMA
            if len(self.ema) > self.max_history_size:
                self.ema = self.ema[-self.max_history_size:]
                
            # Обновляем данные в OrderManager
            self.order_manager.current_ema = self.ema[-1]
            self.order_manager.current_price = self.current_price
            self.order_manager.price_history = self.prices
            
            # Проверяем ордера
            self.order_manager.check_orders(self.current_price)
            
            # Обновляем UI
            if len(self.prices) < 1000 or self.update_counter % 5 == 0:
                self.update_display()
                
            # Обновляем баланс
            if self.update_counter % 10 == 0:
                self.update_balances()

    def stop(self):
        self.stop_simulation = True
        self.timer.stop()
        self.positions_timer.stop()  # Останавливаем таймер для обновления окна позиций
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

        # Для любого режима используем текущую историю цен
        price_data = self.prices[-1000:]  # Последние 1000 точек из актуальной истории цен
        
        # Гарантируем, что ema_data и price_data имеют одинаковую длину
        if len(self.ema) >= len(price_data):
            ema_data = self.ema[-len(price_data):]
        else:
            import numpy as np
            ema_data = [np.nan] * (len(price_data) - len(self.ema)) + self.ema

        logger = logging.getLogger("grid_visualizer")
        logger.debug(f"[GRAPH DATA] price_data={price_data[-5:]} (len={len(price_data)}), ema_data={ema_data[-5:]}, mode={self.simulation_mode}")

        if len(price_data) == 0:
            logger.warning("[GRAPH] price_data пуст — график не обновится")
        
        if self.simulation_mode == "file" and self.file_index > 0:
            # Для режима файла добавляем временные метки, но только для обработанных данных
            # Берем только те метки, которые соответствуют обработанным ценам
            processed_timestamps = [timestamp for timestamp, _, _ in self.file_prices[:self.file_index]]
            timestamps = processed_timestamps[-len(price_data):]  # Берем только последние, соответствующие price_data
            
            self.graph.set_full_data(
                price_data,
                ema_data,
                buy_orders,
                sell_orders,
                self.order_manager.order_history,
                distribution_data,
                timestamps=timestamps
            )
        else:
            # Для режима случайных цен: используем стандартный вывод
            self.graph.set_full_data(
                price_data,
                ema_data,
                buy_orders,
                sell_orders,
                self.order_manager.order_history,
                distribution_data
            )

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

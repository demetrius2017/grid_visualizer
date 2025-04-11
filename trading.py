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

        # Максимальный размер истории для ограничения использования памяти
        self.max_history_size = 10000  
        self.gui_update_interval = 100  # Обновлять UI каждые 100 тиков
        self.update_counter = 0  
        self.timestamps = []  
        self.execution_time_map = {}  # глобальная карта индексов к timestamp
        self.batch_size = 10  # размер пакета обработки данных
        
        if self.simulation_mode == "file" and self.file_prices:
            self.current_price = self.file_prices[0][1]  # Устанавливаем начальную цену из файла
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

        # Создаем таймеры, но НЕ запускаем их здесь
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        # УДАЛЯЕМ self.timer.start(10)
        
        # Отдельный таймер для плавной отрисовки UI
        self.display_timer = QtCore.QTimer()
        self.display_timer.setInterval(33)  # ~30 FPS
        self.display_timer.timeout.connect(self.update_display)
        # НЕ запускаем таймер отображения

        self.update_counter = 0
        self.update_frequency = 1
        self.price_buffer = []

        # Отключаем обработку действий мыши до запуска симуляции
        # self.graph.graphWidget.scene().sigMouseMoved.connect(self.mouse_moved)
        self._mouse_handler_connected = False

        # Создаем отдельный таймер для обновления окна позиций
        self.positions_timer = QtCore.QTimer()
        self.positions_timer.setInterval(1000)  # Обновление каждую секунду
        self.positions_timer.timeout.connect(self.update_positions_window)
        # НЕ запускаем таймер окна позиций
        
        # Флаг для контроля первого запуска симуляции
        self.first_run = True

    def start(self):
        """Запуск симуляции с корректной инициализацией EMA"""
        try:
            self.stop_simulation = False

            # Создаем и показываем окно позиций
            if self.positions_window is None:
                self.positions_window = PositionsWindow()
            self.positions_window.show()

            # Генерация начальных данных для EMA
            print(f"Generating initial data for EMA calculation (period={self.ema_period})")
            if self.simulation_mode == "file" and self.file_prices:
                # Для данных из файла берем реальные цены
                self.prices = [price for _, price, _ in self.file_prices[:self.ema_period]]
                self.current_price = self.prices[-1]
            else:
                # Для случайной генерации начинаем с текущей цены
                start_price = self.current_price if self.current_price else 0.5
                self.prices = [start_price]
                # Генерируем начальные цены для EMA
                for _ in range(self.ema_period - 1):
                    new_price = max(0.001, self.prices[-1] * (1 + np.random.normal(0, self.volatility)))
                    self.prices.append(new_price)
                self.current_price = self.prices[-1]

            # Рассчитываем начальное значение EMA как среднее первых self.ema_period цен
            # Это обеспечит плавный старт EMA с реальных значений
            if len(self.prices) >= self.ema_period:
                initial_ema = np.mean(self.prices[-self.ema_period:])
            else:
                initial_ema = self.prices[-1]  # Если недостаточно данных, берем последнюю цену
                
            self.ema = [initial_ema]
            print(f"Initial EMA calculated: {initial_ema} from price data")

            # Обновляем данные в OrderManager
            self.order_manager.current_ema = initial_ema
            self.order_manager.current_price = self.current_price
            self.order_manager.price_history = self.prices.copy()
            
            # Активируем возможность создания ордеров только при старте симуляции
            self.order_manager.orders_enabled = True
            print("Order creation enabled")

            # Инициализируем сетку
            print("Initializing grid...")
            self.order_manager.initialize_grid()
            
            # Подключаем обработчик мыши только при запуске симуляции
            if not self._mouse_handler_connected:
                self.graph.graphWidget.scene().sigMouseMoved.connect(self.mouse_moved)
                self._mouse_handler_connected = True
                print("Mouse handler connected")

            # Запускаем таймеры
            self.timer.start(10)  # было 50, стало 10 - теперь 100 тиков в секунду
            self.display_timer.start()  # ~30 FPS для отрисовки
            self.positions_timer.start()
            print("Simulation started")

            # Первый отложенный вызов UI
            QtCore.QTimer.singleShot(0, self.update_display)
            
        except Exception as e:
            print(f"Ошибка при запуске симуляции: {e}")
            import traceback
            print(traceback.format_exc())

    def set_csv_file(self, filepath):
        self.csv_filepath = filepath
        self.simulation_mode = "file"
        self.load_price_history_from_csv(filepath)

    def load_price_history_from_csv(self, filepath):
        """Оптимизированная загрузка истории цен с конвертацией временных меток"""
        try:
            import csv
            import datetime
            
            csv_data = []
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)  # Пропускаем заголовок
                
                for row in reader:
                    if len(row) >= 2:
                        try:
                            raw_ts = row[0]
                            # Парсим строку в datetime
                            dt = datetime.datetime.fromisoformat(raw_ts.replace("Z", ""))
                            timestamp = dt.timestamp()  # Конвертируем в Unix timestamp (float)
                            price = float(row[1])
                            source = row[2] if len(row) > 2 else "unknown"
                            
                            csv_data.append((timestamp, price, source))
                        except Exception as e:
                            print(f"Ошибка строки: {row}, {e}")
                            continue
            
            # Сортируем по временной метке
            self.file_prices = sorted(csv_data, key=lambda x: x[0])
            self.file_index = 0
            
            # Сохраняем только временные метки (уже как float)
            self.timestamps = [row[0] for row in self.file_prices]
            
            print(f"Загружено {len(csv_data)} точек данных из '{filepath}'")
            if csv_data:
                print(f"Диапазон времени: {datetime.datetime.fromtimestamp(self.timestamps[0])} - {datetime.datetime.fromtimestamp(self.timestamps[-1])}")
            
            # Если данные загружены, меняем режим
            if self.file_prices:
                self.simulation_mode = "file"
                # Устанавливаем начальную цену
                _, initial_price, _ = self.file_prices[0]
                self.current_price = initial_price
                print(f"Начальная цена установлена: {initial_price}")
            
            return True
            
        except Exception as e:
            print(f"Ошибка при загрузке CSV-файла: {e}")
            import traceback
            print(traceback.format_exc())
            self.simulation_mode = "random"
            return False

    def update(self):
        """Обновление состояния без привязки к отрисовке"""
        try:
            batch_size = self.batch_size
            batch_processed = 0
            timestamps_batch = []
            prices_batch = []

            if self.simulation_mode == "file":
                while batch_processed < batch_size and self.file_index < len(self.file_prices):
                    timestamp, new_price, source = self.file_prices[self.file_index]
                    self.file_index += 1
                    batch_processed += 1

                    # Обновляем цену и время
                    self.current_price = new_price
                    self.current_timestamp = timestamp
                    
                    # Проверяем исполнение ордеров с передачей timestamp
                    self.order_manager.check_orders(self.current_price, timestamp)
                    
                    # Обновляем EMA и проверяем сетку
                    if len(self.ema) > 0:
                        self.order_manager.current_ema = self.ema[-1]
                        # Увеличиваем счётчик проверок сетки
                        self.order_manager.grid_check_counter += 1
                        # Проверяем состояние сетки каждые grid_check_interval тиков
                        if self.order_manager.grid_check_counter >= self.order_manager.grid_check_interval:
                            if self.order_manager.check_grid_state():
                                self.order_manager.update_grid(self.ema[-1], self.current_price, self.prices)
                            self.order_manager.grid_check_counter = 0

                    # Собираем данные
                    timestamps_batch.append(timestamp)
                    prices_batch.append(new_price)
                    
                    # Обновляем историю
                    self.timestamps.append(timestamp)
                    self.prices.append(new_price)

            elif self.simulation_mode == "random":
                while batch_processed < batch_size:
                    # Генерируем следующую цену
                    new_price = self.generate_next_price()
                    timestamp = len(self.prices)  # В random режиме используем индекс как timestamp
                    batch_processed += 1
                    
                    # Обновляем цену и время
                    self.current_price = new_price
                    self.current_timestamp = timestamp

                    # Проверяем исполнение ордеров с передачей timestamp
                    self.order_manager.check_orders(self.current_price, timestamp)

                    # Обновляем EMA и проверяем сетку
                    if len(self.ema) > 0:
                        self.order_manager.current_ema = self.ema[-1]
                        # Увеличиваем счётчик проверок сетки
                        self.order_manager.grid_check_counter += 1
                        # Проверяем состояние сетки каждые grid_check_interval тиков
                        if self.order_manager.grid_check_counter >= self.order_manager.grid_check_interval:
                            if self.order_manager.check_grid_state():
                                self.order_manager.update_grid(self.ema[-1], self.current_price, self.prices)
                            self.order_manager.grid_check_counter = 0

                    # Собираем данные
                    timestamps_batch.append(timestamp)
                    prices_batch.append(new_price)
                    
                    # Обновляем историю
                    self.timestamps.append(timestamp)
                    self.prices.append(new_price)

            # Обновляем EMA
            if len(self.prices) >= self.ema_period:
                k = 2 / (self.ema_period + 1)
                if not self.ema:
                    # Используем начальное значение как среднее первых ema_period цен
                    initial_ema = np.mean(self.prices[-self.ema_period:])
                    self.ema.append(initial_ema)
                    print(f"Starting EMA from actual price average: {initial_ema:.8f}")
                else:
                    # Обычный расчет EMA
                    new_ema = self.current_price * k + self.ema[-1] * (1 - k)
                    self.ema.append(new_ema)
                self.order_manager.current_ema = self.ema[-1]
            elif len(self.prices) > 0:
                # Если данных меньше чем ema_period, используем среднее имеющихся цен
                self.ema.append(np.mean(self.prices))
                self.order_manager.current_ema = self.ema[-1]

            # Обновляем историю в OrderManager
            self.order_manager.price_history = self.prices
            self.order_manager.timestamps = self.timestamps

            # Очистка старых данных для экономии памяти
            if len(self.prices) > self.max_history_size * 1.2:
                self.prices = self.prices[-self.max_history_size:]
                self.ema = self.ema[-min(len(self.ema), self.max_history_size):]
                self.timestamps = self.timestamps[-self.max_history_size:]
                self.balance_history = self.balance_history[-min(len(self.balance_history), self.max_history_size):]
                self.free_margin_history = self.free_margin_history[-min(len(self.free_margin_history), self.max_history_size):]
                self.margin_history = self.margin_history[-min(len(self.margin_history), self.max_history_size):]

        except Exception as e:
            print(f"Ошибка в update: {e}")
            import traceback
            print(traceback.format_exc())

    def reset_update_state(self):
        """Сброс состояния обновления при ошибке"""
        try:
            logger = logging.getLogger("grid_visualizer")
            logger.info("Восстановление состояния обновления после ошибки")
            
            # Проверяем и восстанавливаем критические данные
            if not self.prices:
                self.prices = [self.current_price]
            
            if not self.ema:
                self.ema = [self.current_price]
                
            # Форсированное обновление UI
            self.update_display()
        except Exception as e:
            logger = logging.getLogger("grid_visualizer")
            logger.error(f"Ошибка при восстановлении состояния: {str(e)}")

    def stop(self):
        self.stop_simulation = True
        self.timer.stop()
        self.display_timer.stop()
        self.positions_timer.stop()  # Останавливаем таймер для обновления окна позиций
        
        # Отключаем возможность создания ордеров при остановке симуляции
        self.order_manager.orders_enabled = False
        print("Order creation disabled")
        
        print("Simulation stopped")

    def set_grid_settings(self, settings):
        self.grid_size = settings["grid_size"]
        self.volatility = settings["volatility"]
        self.order_manager.grid_step_percent = self.grid_size
        self.order_manager.volatility = self.volatility
        print(f"Grid settings updated: grid_size={self.grid_size}, volatility={self.volatility}")

    def update_display(self):
        """Обновление отображения графика"""
        try:
            # Определяем видимый диапазон
            visible_range = getattr(self.graph, 'visible_range', 1000)
            
            # Ограничиваем данные видимым диапазоном
            price_data = self.prices[-visible_range:]
            ema_data = self.ema[-visible_range:] if len(self.ema) >= len(price_data) else \
                [np.nan] * (len(price_data) - len(self.ema)) + self.ema

            # Получаем соответствующие временные метки
            if self.simulation_mode == "file" and self.timestamps:
                start_index = max(0, self.file_index - len(price_data))
                current_timestamps = self.timestamps[start_index:self.file_index]
            else:
                current_timestamps = None

            # Автоматическое удаление старых точек из буфера
            max_buffer = visible_range * 2  # Храним в 2 раза больше точек чем visible_range
            if len(self.prices) > max_buffer:
                self.prices = self.prices[-max_buffer:]
            if len(self.ema) > max_buffer:
                self.ema = self.ema[-max_buffer:]

            # Получаем данные из order_manager
            buy_orders = [order for order in self.order_manager.orders if order.order_type == "buy" and not order.executed]
            sell_orders = [order for order in self.order_manager.orders if order.order_type == "sell" and not order.executed]
            order_history = self.order_manager.get_order_history()
            price_distribution = self.order_manager.get_price_distribution() if hasattr(self.order_manager, 'get_price_distribution') else None

            # Обновляем график с передачей карты временных меток
            self.graph.set_full_data(
                price_data,
                ema_data,
                buy_orders,
                sell_orders,
                order_history,
                price_distribution,
                current_timestamps,
                execution_map=self.execution_time_map
            )

        except Exception as e:
            logger = logging.getLogger("grid_visualizer")
            logger.error(f"[TRADING] Ошибка в update_display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

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
        # Убираем дублирующий вызов, так как сделки отрисовываются в update_display()

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
            self.order_manager.current_ema = self.ema[-1]
            self.order_manager.current_price = self.current_price
            self.order_manager.price_history = self.prices.copy()
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
        """Обновляет окно позиций с актуальной информацией"""
        
        # Создаем окно, если оно еще не существует
        if self.positions_window is None:
            self.positions_window = PositionsWindow()
            self.positions_window.show()
            
        # Получаем данные о позициях
        open_positions = self.order_manager.get_open_positions()
        closed_positions = self.order_manager.get_closed_positions()[-100:]  # Последние 100 закрытых позиций
        
        # Получаем актуальные данные о балансе и марже
        current_balance = self.order_manager.get_balance()
        free_margin = self.order_manager.get_free_margin()
        
        # Получаем общую плавающую прибыль 
        floating_profit = self.order_manager.calculate_floating_profit(self.current_price)
        
        # Получаем количество открытых ордеров и общее количество сделок
        open_orders_count = self.order_manager.get_open_orders_count()
        total_trades_count = self.order_manager.get_total_trades_count()
        
        # Получаем информацию о хедже
        active_options = self.order_manager.options_manager.active_options
        options_history = self.order_manager.options_manager.options_history[-50:]  # Последние 50 операций
        
        # Обновляем окно позиций с передачей всех необходимых параметров
        self.positions_window.update_positions(
            open_positions,
            closed_positions,
            self.current_price,
            active_options,
            options_history,
            balance=current_balance,
            free_margin=free_margin,
            floating_profit=floating_profit,
            open_orders_count=open_orders_count,
            total_trades_count=total_trades_count
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

    def cleanup_order_history(self):
        """Очистка истории ордеров, оставляя только значимые"""
        if len(self.order_manager.order_history) > 300:  # Пороговое значение
            # Сохраняем первые 100 ордеров (для истории)
            keep_first = 100
            # Сохраняем последние 200 ордеров (для текущего отображения)
            keep_last = 200
            
            # Создаем новую историю ордеров
            if len(self.order_manager.order_history) > (keep_first + keep_last):
                first_chunk = self.order_manager.order_history[:keep_first]
                last_chunk = self.order_manager.order_history[-keep_last:]
                self.order_manager.order_history = first_chunk + last_chunk
                
                # Логируем для отладки
                logger = logging.getLogger("grid_visualizer")
                logger.info(f"[MEMORY] Очищена история ордеров: {len(self.order_manager.order_history)} ордеров сохранено")

    def manage_orders_history(self):
        """
        Полностью переделанный метод для управления историей ордеров
        """
        # Проверяем количество ордеров в истории
        if len(self.order_manager.order_history) > 300:
            # Сортируем ордера по времени исполнения
            executed_orders = [order for order in self.order_manager.order_history if order.executed]
            executed_orders.sort(key=lambda order: order.execution_time if hasattr(order, 'execution_time') else 0)
            
            # Сохраняем все неисполненные ордера
            non_executed_orders = [order for order in self.order_manager.order_history if not order.executed]
            
            # Оставляем первые 50 и последние 150 исполненных ордеров
            if len(executed_orders) > 200:
                keep_first = 50
                keep_last = 150
                new_executed_orders = executed_orders[:keep_first] + executed_orders[-keep_last:]
                
                # Обновляем историю
                self.order_manager.order_history = non_executed_orders + new_executed_orders
                
                # Логируем для отладки
                logger = logging.getLogger("grid_visualizer")
                logger.info(f"[MEMORY] Очищена история ордеров: осталось {len(self.order_manager.order_history)} из {len(executed_orders) + len(non_executed_orders)}")

    def execute_order(self, order, current_price, index):
        """Исполнение ордера с сохранением временной метки исполнения"""
        try:
            if not order.executed:
                order.execution_price = current_price
                if self.simulation_mode == "file" and self.timestamps:
                    # Используем реальную временную метку из файла
                    order.execution_time = self.timestamps[index]
                else:
                    # В случае random mode используем индекс как временную метку
                    order.execution_time = index
                
                order.executed = True
                
                # Логируем исполнение ордера
                logger = logging.getLogger("grid_visualizer")
                logger.info(
                    f"[ORDER] Executed order ID={order.id}, type={order.order_type}, "
                    f"price={order.execution_price:.8f}, time={order.execution_time}"
                )
                
                return True
        except Exception as e:
            logger = logging.getLogger("grid_visualizer")
            logger.error(f"[ORDER] Error executing order: {str(e)}")
        return False

    def generate_next_price(self):
        """Генерирует следующую цену на основе текущей цены и волатильности"""
        try:
            if not self.current_price:
                self.current_price = 0.5  # начальная цена по умолчанию

            # Генерируем случайное изменение цены с учетом волатильности
            price_change = np.random.normal(0, self.volatility)

            # Применяем изменение к текущей цене
            new_price = max(0.001, self.current_price * (1 + price_change))

            # Ограничиваем максимальное изменение цены для реалистичности
            max_change = 0.1  # максимальное изменение 10%
            if abs(new_price - self.current_price) / self.current_price > max_change:
                if new_price > self.current_price:
                    new_price = self.current_price * (1 + max_change)
                else:
                    new_price = self.current_price * (1 - max_change)
            
            return new_price

        except Exception as e:
            logger = logging.getLogger("grid_visualizer")
            logger.error(f"[PRICE] Ошибка генерации цены: {str(e)}")
            return self.current_price  # в случае ошибки возвращаем текущую цену


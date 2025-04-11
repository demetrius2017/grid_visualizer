from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
import numpy as np
import logging
import datetime
from pyqtgraph import AxisItem


class TimeAxisItem(AxisItem):
    def tickStrings(self, values, scale, spacing):
        """Конвертирует timestamp в читаемый формат времени"""
        try:
            return [datetime.datetime.fromtimestamp(value).strftime("%H:%M") for value in values]
        except Exception:
            return [str(value) for value in values]


class MarketGraph(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.buy_spots = []
        self.sell_spots = []
        self.init_ui()
        self.current_price_line = None
        self.visible_range = 1000  # Количество точек, отображаемых на графике
        self.data_offset = 0  # Смещение данных для скроллинга
        self.distribution_data = None
        self.timestamps = None  # Добавляем поле для хранения временных меток
        self.logger = logging.getLogger("grid_visualizer")
        self.timestamps = None  # Добавляем явную инициализацию timestamps
        
        # Флаги для отслеживания состояния
        self.graph_initialized = False
        self.ema_visible = True
        self.auto_scroll = True  # Флаг для автопрокрутки
        
        # Настраиваем обработку колеса мыши
        self.graphWidget.scene().sigWheelScrolled = self.handle_mouse_wheel
        self.graphWidget.wheelEvent = self.mouse_wheel_event

    def init_ui(self):
        # Основной вертикальный layout
        main_layout = QtWidgets.QVBoxLayout(self)

        # Создаем QSplitter для вертикального разделения
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        # Верхний график (Market Price Simulation) с кастомной осью времени
        self.graphWidget = pg.PlotWidget(axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.graphWidget.setTitle("Market Price Simulation")
        self.graphWidget.setLabel("left", "Price")
        self.graphWidget.setLabel("bottom", "Time (HH:MM)")
        self.graphWidget.showGrid(x=True, y=True)
        
        # Устанавливаем минимальную высоту для графика
        self.graphWidget.setMinimumHeight(250)
        self.graphWidget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        splitter.addWidget(self.graphWidget)

        # Добавляем горизонтальный ползунок для скроллинга
        self.scroll_bar = QtWidgets.QScrollBar(QtCore.Qt.Horizontal)
        self.scroll_bar.valueChanged.connect(self.update_visible_range)
        main_layout.addWidget(self.scroll_bar)

        # Нижний график (Balance, Free Margin, and Margin)
        self.balance_graph = pg.PlotWidget()
        self.balance_graph.setTitle("Balance, Free Margin, and Margin")
        self.balance_graph.setLabel("left", "Value")
        self.balance_graph.setLabel("bottom", "Time")
        self.balance_graph.showGrid(x=True, y=True)
        splitter.addWidget(self.balance_graph)

        # Добавляем график для гистограммы распределения цен
        self.distribution_graph = pg.PlotWidget()
        self.distribution_graph.setTitle("Price Distribution")
        self.distribution_graph.setLabel("left", "Frequency")
        self.distribution_graph.setLabel("bottom", "Price")
        self.distribution_graph.showGrid(x=True, y=True)
        splitter.addWidget(self.distribution_graph)

        # Таблица ордеров
        self.orders_table = QtWidgets.QTableWidget()
        self.orders_table.setColumnCount(6)
        self.orders_table.setHorizontalHeaderLabels(["ID", "Price", "Direction", "Commission", "Volume", "Profit"])
        splitter.addWidget(self.orders_table)

        # Добавляем splitter в основной layout
        main_layout.addWidget(splitter)

        # Отчет
        self.report_label = QtWidgets.QLabel()
        main_layout.addWidget(self.report_label)

        # Добавляем кнопку для управления автопрокруткой
        self.scroll_lock_button = QtWidgets.QPushButton("🔒 Auto-scroll ON")
        self.scroll_lock_button.setCheckable(True)
        self.scroll_lock_button.setChecked(True)
        self.scroll_lock_button.clicked.connect(self.toggle_auto_scroll)
        main_layout.addWidget(self.scroll_lock_button)

        self.init_plot_items()

    def init_plot_items(self):
        # Инициализация элементов графика цены
        self.price_curve = self.graphWidget.plot(pen=pg.mkPen("y", width=1))
        self.ema_curve = self.graphWidget.plot(pen=pg.mkPen("b", width=1))
        self.buy_orders_curve = pg.ScatterPlotItem(
            pen=pg.mkPen("g"), brush=pg.mkBrush(0, 255, 0, 120), symbol="t1", size=10
        )
        self.sell_orders_curve = pg.ScatterPlotItem(
            pen=pg.mkPen("r"), brush=pg.mkBrush(255, 0, 0, 120), symbol="t", size=10
        )
        self.order_history_curve = pg.ScatterPlotItem(pen=pg.mkPen(None), symbol="o", size=5)
        self.graphWidget.addItem(self.buy_orders_curve)
        self.graphWidget.addItem(self.sell_orders_curve)
        self.graphWidget.addItem(self.order_history_curve)
        self.order_book_item = pg.GraphItem()
        self.graphWidget.addItem(self.order_book_item)
        self.graphWidget.setMouseEnabled(x=True, y=False)
        self.graphWidget.setAutoVisible(y=True)

        # Инициализация элементов графика баланса
        self.balance_curve = self.balance_graph.plot(pen=pg.mkPen("g", width=1), name="Balance")
        self.free_margin_curve = self.balance_graph.plot(pen=pg.mkPen("b", width=1), name="Free Margin")
        self.margin_curve = self.balance_graph.plot(pen=pg.mkPen("r", width=1), name="Margin")
        # Инициализация элементов гистограммы
        self.histogram_bars = pg.BarGraphItem(x=[], height=[], width=0.8, brush="g")
        self.normal_curve = self.distribution_graph.plot(pen="r")
        self.current_price_line_hist = pg.InfiniteLine(angle=90, movable=False, pen="b")
        self.distribution_graph.addItem(self.histogram_bars)
        self.distribution_graph.addItem(self.current_price_line_hist)

    def update_distribution_chart(self):
        if self.distribution_data:
            hist = self.distribution_data["hist"]
            bin_edges = self.distribution_data["bin_edges"]
            normal_dist = self.distribution_data["normal_dist"]
            x = self.distribution_data["x"]
            current_price = self.distribution_data["current_price"]

            # Очищаем график перед обновлением
            self.distribution_graph.clear()

            # Создаем новый BarGraphItem для гистограммы
            bar_positions = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(bin_edges) - 1)]
            colors = ["g" if abs(h - n) <= 0.2 else "r" for h, n in zip(hist, normal_dist)]

            # Нормализуем высоту столбцов гистограммы
            max_height = max(max(hist), max(normal_dist))
            normalized_hist = [h / max_height for h in hist]

            self.histogram_bars = pg.BarGraphItem(
                x=bar_positions,
                height=normalized_hist,
                width=(bin_edges[1] - bin_edges[0]) * 0.8,
                brushes=colors,
            )
            self.distribution_graph.addItem(self.histogram_bars)

            # Обновляем нормальную кривую
            normalized_normal_dist = [n / max_height for n in normal_dist]
            self.normal_curve = self.distribution_graph.plot(x, normalized_normal_dist, pen=pg.mkPen("r", width=2))

            # Обновляем линию текущей цены
            self.current_price_line_hist = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("b", width=2))
            self.distribution_graph.addItem(self.current_price_line_hist)
            self.current_price_line_hist.setValue(current_price)

            # Настраиваем оси
            self.distribution_graph.setLabel("left", "Normalized Frequency")
            self.distribution_graph.setLabel("bottom", "Price")

            # Устанавливаем диапазон осей
            x_min, x_max = min(bin_edges), max(bin_edges)
            x_range = x_max - x_min
            self.distribution_graph.setXRange(x_min - 0.1 * x_range, x_max + 0.1 * x_range)
            self.distribution_graph.setYRange(0, 1.1)  # Нормализованный диапазон от 0 до 1

    def update_graph(self, price_data):
        """Обновление графика с использованием временных меток"""
        if not price_data:
            self.logger.warning("[GRAPH] Нет данных для обновления графика")
            return

        try:
            start = max(0, self.data_offset)
            end = min(start + self.visible_range, len(price_data))
            visible_data = price_data[start:end]

            # Определяем X координаты на основе временных меток или индексов
            if self.timestamps and len(self.timestamps) >= end:
                x_data = self.timestamps[start:end]
                # Обновляем scroll_bar на основе индексов, а не временных меток
                if len(price_data) > self.visible_range:
                    self.scroll_bar.setMaximum(len(price_data) - self.visible_range)
                    self.scroll_bar.setPageStep(self.visible_range)
                else:
                    self.scroll_bar.setMaximum(0)
            else:
                x_data = list(range(start, end))

            # Обновляем график
            self.price_curve.setData(x=x_data, y=visible_data)

            # Устанавливаем диапазон осей для текущего набора данных
            if x_data:
                self.graphWidget.setXRange(x_data[0], x_data[-1])

        except Exception as e:
            self.logger.error(f"[GRAPH] Ошибка при обновлении графика: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())

    def update_ema(self, ema_data):
        if ema_data:
            visible_ema = ema_data[self.data_offset : self.data_offset + self.visible_range]
            # Используем те же временные метки, что и для цены
            if self.timestamps and len(self.timestamps) >= self.data_offset + self.visible_range:
                x_data = self.timestamps[self.data_offset : self.data_offset + self.visible_range]
            else:
                x_data = list(range(len(visible_ema)))
            self.ema_curve.setData(x_data, visible_ema)
            self.ema_curve.show()

    def update_report(self, balance, profit, floating_profit, free_margin, total_commission, hedge_metrics):
        """
        Обновленный отчет с информацией о хедже
        """
        self.report_label.setText(
            f"Balance: {balance:.2f}, Profit: {profit:.2f}, "
            f"Floating Profit: {floating_profit:.2f}, "
            f"Free Margin: {free_margin:.2f}, "
            f"Total Commission: {total_commission:.2f}"
        )

    def update_orders_table(self, orders):
        self.orders_table.setRowCount(len(orders))
        for i, order in enumerate(orders):
            self.orders_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(order.id)))
            self.orders_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{order.price:.8f}"))
            self.orders_table.setItem(i, 2, QtWidgets.QTableWidgetItem(order.order_type))
            self.orders_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{order.commission:.8f}"))
            self.orders_table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{order.volume:.8f}"))
            self.orders_table.setItem(i, 5, QtWidgets.QTableWidgetItem(f"{order.profit:.8f}"))

    def update_balance_graph(self, balance_history, free_margin_history, margin_history):
        if balance_history and free_margin_history and margin_history:
            x = list(range(len(balance_history)))
            self.balance_curve.setData(x, balance_history)
            self.free_margin_curve.setData(x, free_margin_history)
            self.margin_curve.setData(x, margin_history)

            # Обновляем диапазон осей
            self.balance_graph.setXRange(0, len(balance_history))
            min_y = min(min(balance_history), min(free_margin_history), min(margin_history))
            max_y = max(max(balance_history), max(free_margin_history), max(margin_history))
            self.balance_graph.setYRange(min_y, max_y)

            # Принудительно обновляем график
            self.balance_graph.update()

    def clear_graph(self):
        self.price_curve.setData([], [])
        self.ema_curve.setData([], [])
        self.buy_orders_curve.setData([])
        self.sell_orders_curve.setData([])
        self.order_history_curve.setData([])
        self.balance_curve.setData([], [])
        self.free_margin_curve.setData([], [])
        self.margin_curve.setData([], [])
        self.orders_table.setRowCount(0)
        self.report_label.setText("")
        print("Graph cleared")

    def auto_scale_view(self):
        """Улучшенный метод автоматического масштабирования представления графика"""
        try:
            if not hasattr(self, 'full_price_data') or not self.full_price_data:
                # if данных нет, но есть текущая цена - используем её
                if hasattr(self, 'current_price') and self.current_price:
                    self.graphWidget.setYRange(
                        self.current_price * 0.9,  # -10% от текущей цены
                        self.current_price * 1.1   # +10% от текущей цены
                    )
                return

            # Используем только видимые данные
            if len(self.full_price_data) >= self.visible_range:
                visible_prices = self.full_price_data[-self.visible_range:]
            else:
                visible_prices = self.full_price_data[:]

            # Добавляем ордера к видимым данным
            if hasattr(self, 'full_buy_orders') and self.full_buy_orders:
                visible_prices.extend([order.price for order in self.full_buy_orders])
            if hasattr(self, 'full_sell_orders') and self.full_sell_orders:
                visible_prices.extend([order.price for order in self.full_sell_orders])

            if visible_prices:
                min_price = min(visible_prices)
                max_price = max(visible_prices)
                price_range = max_price - min_price

                # Добавляем отступы для лучшей видимости (15% от диапазона цен)
                padding = price_range * 0.15 if price_range > 0 else min_price * 0.15
                self.graphWidget.setYRange(
                    min_price - padding,
                    max_price + padding
                )

                # Устанавливаем видимый диапазон по X
                visible_points = min(len(self.full_price_data), self.visible_range)
                if visible_points > 0:
                    if self.timestamps and len(self.timestamps) >= visible_points:
                        self.graphWidget.setXRange(
                            self.timestamps[0],
                            self.timestamps[-1]
                        )
                    else:
                        self.graphWidget.setXRange(0, visible_points)

        except Exception as e:
            self.logger.error(f"[GRAPH] Ошибка в auto_scale_view: {str(e)}")

    def update_visible_range(self, value=None):
        """
        Оптимизированная версия метода обновления видимого диапазона
        с поддержкой временных меток и правильным позиционированием ордеров
        """
        try:
            if not hasattr(self, 'full_price_data') or not self.full_price_data:
                return

            # Фиксируем размер видимого диапазона
            if len(self.full_price_data) > 1000:
                self.visible_range = min(self.visible_range, 500)
            
            if value is not None:
                self.data_offset = value
                # Если пользователь вручную двигает ползунок и он не в конце
                if value < self.scroll_bar.maximum():
                    self.auto_scroll = False
                    self.scroll_lock_button.setChecked(False)
                    self.scroll_lock_button.setText("🔓 Auto-scroll OFF")
            else:
                self.data_offset = max(0, len(self.full_price_data) - self.visible_range)
            
            start = max(0, self.data_offset)
            end = min(start + self.visible_range, len(self.full_price_data))
            
            visible_data = self.full_price_data[start:end]
            if not visible_data:
                return
                
            # Используем временные метки, if они доступны
            if self.timestamps and len(self.timestamps) >= end:
                x_data = self.timestamps[start:end]
            else:
                x_data = list(range(len(visible_data)))
            
            # Отрисовываем ценовой график
            self.price_curve.setData(x_data, visible_data)
            
            # Обновляем EMA
            if hasattr(self, 'full_ema_data') and self.full_ema_data:
                visible_ema = self.full_ema_data[start:end] if len(self.full_ema_data) >= end else []
                if visible_ema or len(visible_ema) == len(x_data):
                    self.ema_curve.setData(x_data, visible_ema)
                    self.ema_curve.show() if self.ema_visible else self.ema_curve.hide()

            # Обновляем ордера с правильным позиционированием по времени
            if visible_data:
                current_time = x_data[-1] if x_data else len(visible_data) - 1
                self.update_order_book(
                    self.full_buy_orders,
                    self.full_sell_orders,
                    current_time,
                    visible_data[-1]
                )

            # Обновляем историю ордеров с учётом временных меток
            self.update_order_history_aligned(self.full_order_history, start, x_data)
            
            # Автоматически масштабируем по оси Y при скролле
            self.auto_scale_view()
            
            # Автопрокрутка только если включена
            if self.auto_scroll:
                self.scroll_bar.setValue(self.scroll_bar.maximum())
            
        except Exception as e:
            self.logger.error(f"[GRAPH] Ошибка при обновлении видимого диапазона: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())

    def update_order_book(self, buy_orders, sell_orders, current_time, current_price):
        try:
            # Используем значение current_time как базу для размещения ордеров
            x_base = current_time
            
            buy_positions = []
            sell_positions = []
            
            # Размещаем buy ордера справа от текущего времени
            for i, order in enumerate(buy_orders):
                x_pos = x_base + (i + 1)  # Смещаем каждый ордер на 1 шаг
                buy_positions.append({"pos": (x_pos, order.price)})
            
            # Размещаем sell ордера справа от buy ордеров
            offset = len(buy_orders) + 1
            for i, order in enumerate(sell_orders):
                x_pos = x_base + (i + offset + 1)
                sell_positions.append({"pos": (x_pos, order.price)})
            
            # Обновляем данные
            if buy_positions:
                self.buy_orders_curve.setData(pos=np.array([p["pos"] for p in buy_positions]))
            if sell_positions:
                self.sell_orders_curve.setData(pos=np.array([p["pos"] for p in sell_positions]))
                
        except Exception as e:
            self.logger.error(f"[GRAPH] Ошибка при обновлении ордеров: {str(e)}")
            
        return True

    def update_order_history(self, order_history, execution_map=None):
        visible_history = order_history[-self.visible_range:]
        history_spots = []
        
        for order in visible_history:
            if not order.executed or not hasattr(order, 'execution_price') or order.execution_price is None:
                continue
                
            # Используем карту времени исполнения, если доступна
            if execution_map and order.execution_time in execution_map:
                x_coord = execution_map[order.execution_time]
            elif self.timestamps and order.execution_time is not None and order.execution_time < len(self.timestamps):
                x_coord = self.timestamps[order.execution_time]
            else:
                x_coord = order.execution_time

            # Детальное логирование
            self.logger.debug(
                f"[ORDER-HISTORY] Order ID={order.id} @t={order.execution_time}, "
                f"x={x_coord}, y={order.execution_price}, type={order.order_type}"
            )
                
            spot = {
                "pos": (x_coord, order.execution_price),
                "data": 1,
                "brush": pg.mkBrush(0, 255, 0, 220) if order.order_type == "buy" else pg.mkBrush(255, 0, 0, 220),
                "symbol": 'o',
                "size": 15
            }
            history_spots.append(spot)
        
        self.order_history_curve.setData(history_spots)
        if history_spots:
            self.logger.debug(f"[HISTORY] Отрисовано {len(history_spots)} сделок на графике цены")

    def update_order_history_aligned(self, order_history, start_offset, x_data):
        """
        Исправленная функция обновления истории ордеров с корректной привязкой к временным меткам
        """
        try:
            # Сохраняем существующий подход, но исправляем позиционирование
            max_visible_history = 100
            recent_history = [order for order in order_history if order.executed and hasattr(order, 'execution_time') and order.execution_time is not None]
            
            # Сортируем ордера по времени исполнения для корректного отображения
            recent_history.sort(key=lambda order: order.execution_time)
            
            # Ограничиваем количество отображаемых ордеров
            if len(recent_history) > max_visible_history:  
                recent_history = recent_history[-max_visible_history:]
            
            self.logger.debug(f"[ORDER-HISTORY] Processing orders. start_offset={start_offset}, x_data_len={len(x_data)}")
            
            # Создаем массив данных для графика
            history_spots = []
            
            # Правильное позиционирование маркеров
            for order in recent_history:
                # Проверяем правильность позиции исполнения
                if not hasattr(order, 'execution_time') or order.execution_time is None:
                    continue
                
                # Проверяем, что execution_time попадает в видимый диапазон
                if not (start_offset <= order.execution_time < start_offset + len(x_data)):
                    self.logger.debug(
                        f"[ORDER-HISTORY] Skipping Order ID={order.id} - out of range. "
                        f"execution_time={order.execution_time} not in [{start_offset}, {start_offset + len(x_data)}]"
                    )
                    continue
                
                # Безопасно получаем позицию относительно текущего диапазона
                abs_position = min(max(0, int(order.execution_time)), len(self.full_price_data) - 1)
                rel_position = abs_position - start_offset

                # Новый безопасный способ получения координаты X
                if hasattr(self, 'execution_map') and self.execution_map and order.execution_time in self.execution_map:
                    x_coord = self.execution_map[order.execution_time]
                    self.logger.debug(
                        f"[ORDER-HISTORY] Using execution_map for Order ID={order.id}: "
                        f"execution_time={order.execution_time}, x_coord={x_coord}"
                    )
                elif 0 <= rel_position < len(x_data):
                    x_coord = x_data[rel_position]
                    self.logger.debug(
                        f"[ORDER-HISTORY] Using x_data for Order ID={order.id}: "
                        f"rel_position={rel_position}, x_coord={x_coord}"
                    )
                else:
                    self.logger.debug(
                        f"[ORDER-HISTORY] Skipping Order ID={order.id}: invalid position calculation"
                    )
                    continue

                # Создаем точку с корректными координатами
                spot = {
                    "pos": (x_coord, order.execution_price),
                    "data": order.id,
                    "brush": pg.mkBrush(0, 255, 0, 200) if order.order_type == "buy" else pg.mkBrush(255, 0, 0, 200),
                    "symbol": 'o',
                    "size": 10
                }
                history_spots.append(spot)
                
                self.logger.debug(
                    f"[ORDER-HISTORY] Added spot for Order ID={order.id}: "
                    f"x={x_coord}, y={order.execution_price}, type={order.order_type}"
                )
            
            # Обновляем данные кривой истории ордеров
            self.order_history_curve.setData(history_spots)
            self.logger.debug(f"[ORDER-HISTORY] Updated {len(history_spots)} spots on graph")
            
        except Exception as e:
            self.logger.error(f"[GRAPH] Ошибка в update_order_history_aligned: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())

    def set_full_data(self, prices, ema_values, buy_orders, sell_orders, order_history, price_distribution, timestamps=None, execution_map=None):
        """Установка полных данных для графика"""
        try:
            self.prices = prices
            self.ema_values = ema_values
            self.buy_orders = buy_orders
            self.sell_orders = sell_orders
            
            # Ограничиваем историю ордеров видимым диапазоном
            visible_range = getattr(self, 'visible_range', 1000)
            visible_order_history = order_history[-visible_range:] if order_history else []
            self.full_order_history = visible_order_history
            
            self.price_distribution = price_distribution
            self.timestamps = timestamps
            self.execution_map = execution_map  # сохраняем мапу для отрисовки сделок

            # Обновляем все графики
            self.update_plot_data()
            
            # Всегда показывать правый край графика
            self.scroll_bar.setValue(self.scroll_bar.maximum())
            
        except Exception as e:
            logger = logging.getLogger("grid_visualizer")
            logger.error(f"[GRAPH] Ошибка в set_full_data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    def update_hedge_info(self, active_options, current_price):
        """
        Обновление информации о хеджирующих позициях
        """
        self.hedge_table.setRowCount(len(active_options) * 2)  # 2 опциона на позицию

        row = 0
        for position in active_options:
            # Put option
            self.hedge_table.setItem(row, 0, QtWidgets.QTableWidgetItem("Put"))
            self.hedge_table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{position['put']['strike']:.8f}"))
            self.hedge_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{position['put']['premium']:.8f}"))
            self.hedge_table.setItem(
                row,
                3,
                QtWidgets.QTableWidgetItem(f"{position['put']['expiry']*365:.1f} days"),
            )
            put_value = max(0, position["put"]["strike"] - current_price)
            self.hedge_table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{put_value:.8f}"))

            # Call option
            row += 1
            self.hedge_table.setItem(row, 0, QtWidgets.QTableWidgetItem("Call"))
            self.hedge_table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{position['call']['strike']:.8f}"))
            self.hedge_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{position['call']['premium']:.8f}"))
            self.hedge_table.setItem(
                row,
                3,
                QtWidgets.QTableWidgetItem(f"{position['call']['expiry']*365:.1f} days"),
            )
            call_value = max(0, current_price - position["call"]["strike"])
            self.hedge_table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{call_value:.8f}"))
            row += 1

    def process_timestamps(self, timestamps, data_length):
        """Улучшенная обработка временных меток для корректного отображения на графике"""
        try:
            if not timestamps or len(timestamps) < 2:
                self.logger.warning("[GRAPH] Недостаточно временных меток, использую последовательную нумерацию")
                return list(range(data_length))
                    
            # Проверяем тип временных меток
            if isinstance(timestamps[0], str):
                # Пытаемся конвертировать строковые метки в числа для построения графика
                import datetime
                
                # Пробуем разные форматы даты/времени
                formats = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M:%S,%f",
                    "%Y-%m-%d",
                    "%H:%M:%S"
                ]
                
                numeric_timestamps = []
                for ts in timestamps:
                    parsed = None
                    for fmt in formats:
                        try:
                            parsed = datetime.datetime.strptime(ts, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if parsed is not None:
                        # Конвертируем в timestamp
                        numeric_timestamps.append(datetime.datetime.timestamp(parsed))
                    else:
                        # if не удалось распарсить, используем порядковый номер
                        numeric_timestamps.append(len(numeric_timestamps))
                
                # Убеждаемся, что количество меток соответствует длине данных
                if len(numeric_timestamps) < data_length:
                    # Дополняем недостающие метки
                    numeric_timestamps.extend(range(
                        numeric_timestamps[-1] + 1,
                        numeric_timestamps[-1] + 1 + (data_length - len(numeric_timestamps))
                    ))
                elif len(numeric_timestamps) > data_length:
                    # Обрезаем лишние метки
                    numeric_timestamps = numeric_timestamps[:data_length]
                    
                return numeric_timestamps
            else:
                # if метки уже числовые, просто корректируем длину
                if len(timestamps) < data_length:
                    # Дополняем недостающие метки
                    return timestamps + list(range(
                        int(timestamps[-1]) + 1,
                        int(timestamps[-1]) + 1 + (data_length - len(timestamps))
                    ))
                elif len(timestamps) > data_length:
                    # Обрезаем лишние метки
                    return timestamps[:data_length]
                return timestamps
                
        except Exception as e:
            self.logger.error(f"[GRAPH] Ошибка при обработке временных меток: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return list(range(data_length))

    def setup_time_axis(self):
        """Настройка оси X для отображения временных меток в читаемом формате"""
        class TimeAxisItem(pg.AxisItem):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.setLabel(text='Time', units=None)
                self.enableAutoSIPrefix(False)
                
            def tickStrings(self, values, scale, spacing):
                import datetime
                result = []
                for value in values:
                    try:
                        # Всегда рендерим как HH:MM:SS
                        dt = datetime.datetime.fromtimestamp(value)
                        result.append(dt.strftime("%H:%M:%S"))
                    except Exception:
                        result.append(str(int(value)))
                return result
        
        # Заменяем стандартную ось X на настраиваемую
        self.graphWidget.getPlotItem().setAxisItems({'bottom': TimeAxisItem(orientation='bottom')})

    def update_display(self):
        """Обновляет отображение графика"""
        # ...existing code...
        
        if not self.show_continue_dialog():
            return False
            
        # ...existing code...
        return True

    def show_continue_dialog(self):
        """Показывает диалог подтверждения для продолжения итерации"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Подтверждение",
            "Продолжить итерацию?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        return reply == QtWidgets.QMessageBox.Yes

    def update_plot_data(self):
        """Обновление данных графика"""
        try:
            # Обновляем основной график цены
            if hasattr(self, 'prices') and self.prices:
                self.full_price_data = self.prices
                self.update_graph(self.prices)

            # Обновляем EMA
            if hasattr(self, 'ema_values') and self.ema_values:
                self.full_ema_data = self.ema_values
                self.update_ema(self.ema_values)

            # Обновляем ордера
            if hasattr(self, 'buy_orders'):
                self.full_buy_orders = self.buy_orders
            if hasattr(self, 'sell_orders'):
                self.full_sell_orders = self.sell_orders

            # Обновляем историю ордеров
            if hasattr(self, 'full_order_history'):
                self.update_order_history(self.full_order_history)

            # Обновляем распределение цен
            if hasattr(self, 'price_distribution') and self.price_distribution:
                self.distribution_data = self.price_distribution
                self.update_distribution_chart()

            # Автоматически масштабируем вид
            self.auto_scale_view()

        except Exception as e:
            logger = logging.getLogger("grid_visualizer")
            logger.error(f"[GRAPH] Ошибка в update_plot_data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    def toggle_auto_scroll(self):
        """Переключает режим автопрокрутки"""
        self.auto_scroll = self.scroll_lock_button.isChecked()
        self.scroll_lock_button.setText("🔒 Auto-scroll ON" if self.auto_scroll else "🔓 Auto-scroll OFF")
        if self.auto_scroll:
            # Если включаем автопрокрутку, сразу прокручиваем к последним данным
            self.scroll_bar.setValue(self.scroll_bar.maximum())

    def mouse_wheel_event(self, ev):
        """Обработчик события колеса мыши"""
        self.handle_mouse_wheel(ev)
        ev.accept()  # блокируем стандартный zoom

    def handle_mouse_wheel(self, ev):
        """Обработка прокрутки для изменения масштаба"""
        try:
            delta = ev.delta() if hasattr(ev, 'delta') else ev.angleDelta().y()
            # Прокрутка вверх — уменьшить visible_range, вниз — увеличить
            step = -int(delta / 120) * 50  # каждый шаг мыши на 50 точек
            new_range = max(50, min(1000, self.visible_range + step))
            if new_range != self.visible_range:
                self.visible_range = new_range
                self.update_visible_range()
                self.logger.debug(f"[ZOOM] Новый visible_range: {self.visible_range}")
        except Exception as e:
            self.logger.error(f"[ZOOM] Ошибка при масштабировании: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())



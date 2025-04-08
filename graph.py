from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg


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
        
        # Флаги для отслеживания состояния
        self.graph_initialized = False
        self.ema_visible = True

    def init_ui(self):
        # Основной вертикальный layout
        main_layout = QtWidgets.QVBoxLayout(self)

        # Создаем QSplitter для вертикального разделения
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        # Верхний график (Market Price Simulation)
        self.graphWidget = pg.PlotWidget()
        self.graphWidget.setTitle("Market Price Simulation")
        self.graphWidget.setLabel("left", "Price")
        self.graphWidget.setLabel("bottom", "Time")
        self.graphWidget.showGrid(x=True, y=True)
        # Устанавливаем минимальную высоту для графика, чтобы избежать его исчезновения
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
        if not price_data:
            print("[GRAPH] Нет данных для обновления графика")
            return

        if len(price_data) > self.visible_range:
            self.scroll_bar.setMaximum(len(price_data) - self.visible_range)
            self.scroll_bar.setPageStep(self.visible_range)
        else:
            self.scroll_bar.setMaximum(0)

        visible_data = price_data[self.data_offset : self.data_offset + self.visible_range]

        if not visible_data:
            print("[GRAPH] Видимые данные отсутствуют")
            return

        self.price_curve.setData(range(len(visible_data)), visible_data)
        self.graphWidget.setXRange(0, len(visible_data))

    def update_ema(self, ema_data):
        if ema_data:
            visible_ema = ema_data[self.data_offset : self.data_offset + self.visible_range]
            self.ema_curve.setData(range(len(visible_ema)), visible_ema)
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
        """Метод для автоматического масштабирования представления графика"""
        if not self.full_price_data:
            return

        # Получаем все цены, включая ордера
        all_prices = self.full_price_data[:]
        all_prices.extend([order.price for order in self.full_buy_orders])
        all_prices.extend([order.price for order in self.full_sell_orders])

        if all_prices:
            # Находим min и max цены
            min_price = min(all_prices)
            max_price = max(all_prices)
            price_range = max_price - min_price

            # Добавляем отступы для лучшей видимости
            padding = price_range * 0.2  # 20% отступ
            self.graphWidget.setYRange(min_price - padding, max_price + padding)

            # Устанавливаем диапазон по X для отображения последних N свечей
            visible_points = min(len(self.full_price_data), self.visible_range * 2)  # Увеличиваем видимый диапазон
            if visible_points > 0:
                start_index = max(0, len(self.full_price_data) - visible_points)
                self.graphWidget.setXRange(start_index, len(self.full_price_data))

    def update_visible_range(self, value=None):
        """
        Полностью переработанный метод обновления видимого диапазона с жестким контролем координат
        """
        import numpy as np
        
        # Проверка наличия данных
        if not hasattr(self, 'full_price_data') or not self.full_price_data:
            print("[GRAPH] Нет данных для отображения")
            return
            
        # Обновляем смещение
        if value is not None:
            self.data_offset = value
        else:
            self.data_offset = max(0, len(self.full_price_data) - self.visible_range)

        # Вычисляем границы видимого диапазона
        end = min(self.data_offset + self.visible_range, len(self.full_price_data))
        start = max(0, self.data_offset)
        
        if start >= end:
            print(f"[GRAPH] Некорректный диапазон: start={start}, end={end}")
            return
            
        # Данные для ценового графика
        visible_data = self.full_price_data[start:end]
        
        # Создаем строго последовательные координаты X
        x_data = list(range(len(visible_data)))
        
        # Отрисовываем ценовой график
        self.price_curve.setData(x=x_data, y=visible_data)
        print(f"[PRICE] Отрисовано {len(visible_data)} точек цены")
        
        # Обрабатываем EMA данные
        if hasattr(self, 'full_ema_data') and self.full_ema_data:
            # Подготавливаем EMA в том же диапазоне что и цены
            if len(self.full_ema_data) >= end:
                ema_data = self.full_ema_data[start:end]
            else:
                # Если EMA короче, берем что есть и выравниваем длину
                ema_len = len(self.full_ema_data)
                if start >= ema_len:
                    ema_data = []
                else:
                    ema_data = self.full_ema_data[start:min(end, ema_len)]
                    # Дополняем до нужной длины, если надо
                    if len(ema_data) < len(visible_data):
                        ema_data = ema_data + [np.nan] * (len(visible_data) - len(ema_data))
            
            # Фильтруем NaN и создаем точки для EMA
            valid_indices = []
            valid_values = []
            for i, val in enumerate(ema_data):
                if not np.isnan(val):
                    valid_indices.append(i)  # Используем тот же индекс что и на графике цены
                    valid_values.append(val)
            
            # Отрисовываем EMA если есть валидные точки
            if valid_indices:
                self.ema_curve.setData(x=valid_indices, y=valid_values)
                self.ema_curve.show()
                print(f"[EMA] Отрисовано {len(valid_indices)} валидных точек")
            else:
                self.ema_curve.hide()
                print("[EMA] Нет валидных точек для отображения")
        else:
            self.ema_curve.hide()
        
        # Сохраняем видимый диапазон для других методов
        self.visible_x_range = (0, len(visible_data) - 1)
        
        # Сетка ордеров - всегда отображается в правой части графика
        self.update_order_book(
            self.full_buy_orders, 
            self.full_sell_orders,
            current_time=len(visible_data) - 1,  # Последняя точка
            current_price=visible_data[-1] if visible_data else 0
        )
        
        # История сделок
        if hasattr(self, 'full_order_history'):
            self.update_order_history(self.full_order_history)
        
        # Устанавливаем диапазон осей
        self.graphWidget.setXRange(0, len(visible_data) - 1)
        
        # Вычисляем диапазон Y для графика
        if visible_data:
            y_values = list(visible_data)
            if valid_values:
                y_values.extend(valid_values)
            
            min_y = min(y_values) if y_values else 0
            max_y = max(y_values) if y_values else 1
            padding = (max_y - min_y) * 0.1
            
            self.graphWidget.setYRange(min_y - padding, max_y + padding)
        
        # Принудительное обновление графика
        self.graphWidget.update()
        self.graphWidget.repaint()

    def update_order_book(self, buy_orders, sell_orders, current_time, current_price):
        """
        Обновленная версия метода для отображения сетки ордеров справа от графика
        """
        # Получаем текущий диапазон X графика
        x_range = self.graphWidget.getViewBox().viewRange()[0]
        x_min, x_max = x_range
        
        # Используем правую границу графика для размещения сетки ордеров
        x_base = x_max - 5  # Отступ 5 единиц от правого края
        
        # Фильтруем ордера
        visible_buy_orders = buy_orders[-self.visible_range:]
        visible_sell_orders = sell_orders[-self.visible_range:]
        
        buy_positions = []
        sell_positions = []
        
        # Размещаем buy ордера справа
        for i, order in enumerate(visible_buy_orders):
            # Располагаем ордера справа с равным интервалом
            x_pos = x_base - (len(visible_buy_orders) - i) * 0.5
            buy_positions.append({"pos": (x_pos, order.price)})
        
        # Размещаем sell ордера справа
        for i, order in enumerate(visible_sell_orders):
            # Располагаем ордера справа с равным интервалом
            x_pos = x_base - (len(visible_sell_orders) - i) * 0.5
            sell_positions.append({"pos": (x_pos, order.price)})
        
        # Устанавливаем сетку ордеров
        self.buy_orders_curve.setData(buy_positions)
        self.sell_orders_curve.setData(sell_positions)
        
        # Обновляем линию текущей цены
        if self.current_price_line is None:
            self.current_price_line = pg.InfiniteLine(pos=x_base, angle=90, pen=pg.mkPen("w", width=1))
            self.graphWidget.addItem(self.current_price_line)
        else:
            self.current_price_line.setValue(x_base)
            
        # Принудительное обновление
        self.graphWidget.update()

    def update_order_history(self, order_history):
        """
        Обновленная версия метода для корректного отображения сделок на графике
        """
        visible_history = order_history[-self.visible_range:]
        history_spots = []
        
        # Если нет истории или видимых данных, выходим
        if not visible_history or not hasattr(self, 'x_data_filtered'):
            return
            
        # Получаем текущий диапазон X графика
        x_range = self.graphWidget.getViewBox().viewRange()[0]
        x_min, x_max = x_range
        
        # Равномерно распределяем сделки по графику для лучшей видимости
        for i, order in enumerate(visible_history):
            if order.executed and hasattr(order, 'execution_price') and order.execution_price is not None:
                try:
                    # Размещаем сделки равномерно в диапазоне от 20% до 80% ширины графика
                    # Это обеспечивает хорошую видимость и предотвращает наложение сделок
                    position_ratio = i / max(1, len(visible_history) - 1)
                    x_coord = x_min + (x_max - x_min) * (0.2 + 0.6 * position_ratio)
                    
                    spot = {
                        "pos": (x_coord, order.execution_price),
                        "data": 1,
                        "brush": pg.mkBrush(0, 255, 0, 220) if order.order_type == "buy" else pg.mkBrush(255, 0, 0, 220),
                        "symbol": 'o',
                        "size": 15  # Увеличенный размер для лучшей видимости
                    }
                    history_spots.append(spot)
                except Exception as e:
                    print(f"[ERROR] Не удалось отобразить сделку: {e}")
        
        # Обновляем точки сделок
        self.order_history_curve.setData(history_spots)
        
        # Выводим информацию о количестве отрисованных сделок
        if history_spots:
            print(f"[HISTORY] Отрисовано {len(history_spots)} сделок на графике цены")
            
        # Принудительное обновление
        self.graphWidget.update()

    def set_full_data(
        self, price_data, ema_data, buy_orders, sell_orders, order_history, distribution_data, timestamps=None
    ):
        """
        Полностью обновленный метод инициализации данных графика с корректной обработкой NaN в EMA
        """
        import numpy as np
        
        if not price_data:
            print("[GRAPH] Получены пустые данные цены, график не будет обновлён.")
            return

        # Сохраняем исходные данные
        self.full_price_data = price_data
        self.full_ema_data = ema_data
        self.full_buy_orders = buy_orders
        self.full_sell_orders = sell_orders
        self.full_order_history = order_history
        self.timestamps = timestamps
        self.distribution_data = distribution_data
        
        # Фильтрация NaN из EMA данных
        valid_indices = []
        valid_ema = []
        
        for i, ema_val in enumerate(ema_data):
            if not np.isnan(ema_val):
                valid_indices.append(i)
                valid_ema.append(ema_val)
        
        # Сохраняем отфильтрованные данные EMA
        if valid_indices:
            # Создаем полные массивы данных с валидными значениями EMA
            self.filtered_ema_indices = valid_indices
            self.filtered_ema_values = valid_ema
            print(f"[EMA] Отфильтровано {len(valid_ema)} валидных значений EMA из {len(ema_data)}")
        else:
            self.filtered_ema_indices = []
            self.filtered_ema_values = []
            print("[EMA] Все значения EMA являются NaN")
        
        # Установка максимального значения скроллбара
        visible_range = min(self.visible_range, len(price_data))
        max_offset = max(0, len(price_data) - visible_range)
        self.scroll_bar.setMaximum(max_offset)
        self.scroll_bar.setPageStep(visible_range)
        
        # Устанавливаем смещение на конец данных и обновляем видимую область
        self.data_offset = max_offset
        self.scroll_bar.setValue(self.data_offset)
        
        # Устанавливаем флаг инициализации графика
        self.graph_initialized = True
        
        # Обновляем распределение
        self.update_distribution_chart()
        
        # Принудительно вызываем обновление с правильным смещением
        self.update_visible_range(self.data_offset)
        
        # Выводим отладочную информацию
        print(f"[GRAPH] Данные установлены: {len(price_data)} точек цены, {len(valid_ema)} валидных точек EMA")
        
        # Принудительное обновление всего графика
        self.graphWidget.update()
        self.graphWidget.repaint()

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

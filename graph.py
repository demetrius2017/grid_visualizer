from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg


class MarketGraph(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.buy_spots = []
        self.sell_spots = []
        self.init_ui()
        self.current_price_line = None

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
        splitter.addWidget(self.graphWidget)

        # Нижний график (Balance, Free Margin, and Margin)
        self.balance_graph = pg.PlotWidget()
        self.balance_graph.setTitle("Balance, Free Margin, and Margin")
        self.balance_graph.setLabel("left", "Value")
        self.balance_graph.setLabel("bottom", "Time")
        self.balance_graph.showGrid(x=True, y=True)
        splitter.addWidget(self.balance_graph)

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

        # Инициализация элементов графика баланса
        self.balance_curve = self.balance_graph.plot(pen=pg.mkPen("g", width=1), name="Balance")
        self.free_margin_curve = self.balance_graph.plot(pen=pg.mkPen("b", width=1), name="Free Margin")
        self.margin_curve = self.balance_graph.plot(pen=pg.mkPen("r", width=1), name="Margin")

    def update_graph(self, price_data):
        self.price_curve.setData(range(len(price_data)), price_data)

    def update_ema(self, ema_data):
        if ema_data:
            # Убедимся, что длина ema_data соответствует длине данных цены
            x_data = range(len(self.price_curve.getData()[0]))
            y_data = ema_data[-len(x_data) :]  # Берем только последние значения EMA, соответствующие данным цены
            self.ema_curve.setData(x_data, y_data)
            self.ema_curve.show()
        else:
            print("No EMA data to display")

    def update_order_book(self, buy_orders, sell_orders, current_time, current_price):
        # Фильтруем ордера
        buy_orders = [order for order in buy_orders if order.price <= current_price]
        sell_orders = [order for order in sell_orders if order.price >= current_price]
        
        buy_prices = [order.price for order in buy_orders]
        sell_prices = [order.price for order in sell_orders]
        
        print(f"Update order book: Buy orders: {len(buy_orders)}, Sell orders: {len(sell_orders)}")
        
        all_prices = buy_prices + sell_prices + [current_price]
        if len(all_prices) <= 1:
            print("Not enough prices for order book update")
            self.buy_orders_curve.setData([])
            self.sell_orders_curve.setData([])
            return

        min_price = min(all_prices)
        max_price = max(all_prices)
        price_range = max_price - min_price

        # Добавляем небольшой отступ сверху и снизу для лучшей визуализации
        padding = price_range * 0.1
        min_display_price = min_price - padding
        max_display_price = max_price + padding

        buy_positions = []
        sell_positions = []

        for order in buy_orders:
            buy_positions.append({'pos': (current_time, order.price)})

        for order in sell_orders:
            sell_positions.append({'pos': (current_time, order.price)})

        print(f"Plotted buy positions: {len(buy_positions)}, sell positions: {len(sell_positions)}")

        self.buy_orders_curve.setData(buy_positions)
        self.sell_orders_curve.setData(sell_positions)

        # Обновляем диапазон осей Y
        self.graphWidget.setYRange(min_display_price, max_display_price)

        # Обновляем линию текущей цены
        if self.current_price_line is None:
            self.current_price_line = pg.InfiniteLine(pos=current_price, angle=0, pen=pg.mkPen('w', width=1))
            self.graphWidget.addItem(self.current_price_line)
        else:
            self.current_price_line.setPos(current_price)

    def update_order_history(self, order_history):
        history_spots = []
        for order in order_history:
            if order.executed:
                spot = {
                    "pos": (order.execution_time, order.execution_price),
                    "data": 1,
                    "brush": pg.mkBrush("g") if order.order_type == "buy" else pg.mkBrush("r"),
                }
                history_spots.append(spot)
        self.order_history_curve.setData(history_spots)

    def update_report(self, balance, profit, floating_profit, free_margin):
        self.report_label.setText(
            f"Balance: {balance}, Profit: {profit}, Floating Profit: {floating_profit}, Free Margin: {free_margin}"
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
            self.balance_curve.setData(range(len(balance_history)), balance_history)
            self.free_margin_curve.setData(range(len(free_margin_history)), free_margin_history)
            self.margin_curve.setData(range(len(margin_history)), margin_history)

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

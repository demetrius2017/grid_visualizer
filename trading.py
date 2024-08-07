import numpy as np
from PyQt5 import QtCore, QtGui
from orders import OrderManager

class TradingSimulator:
    def __init__(self, graph):
        self.graph = graph
        self.grid_step = 0.01  # Шаг сетки, можно настроить
        self.order_manager = OrderManager(self.grid_step)
        self.current_price = 0.5
        self.volatility = 0.005
        self.stop_simulation = True
        self.grid_size = 20
        self.grid_step = 0.08  # Шаг сетки, измените на нужное значение
        self.grid_levels = 5  # Количество уровней ордеров в каждую сторону

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)

        self.graph.graphWidget.setFocusPolicy(QtCore.Qt.StrongFocus)  # Устанавливаем фокусировку на виджет графика
        self.graph.graphWidget.keyPressEvent = self.key_pressed  # Связываем событие нажатия клавиши с нашим методом

    def start(self):
        self.stop_simulation = False
        self.init_grid_orders()  # Инициализируем сетку ордеров при старте
        self.timer.start(50)

    def init_grid_orders(self):
        # Очистим старые ордера перед созданием новой сетки
        self.order_manager.clear_orders()
        # Размещение сетки ордеров вокруг текущей цены
        for i in range(-self.grid_levels, self.grid_levels + 1):
            price_level = self.current_price + i * self.grid_step
            if i < 0:
                self.order_manager.place_order('buy', price_level, volume=1)  # Покупаем ниже текущей цены
            elif i > 0:
                self.order_manager.place_order('sell', price_level, volume=1)  # Продаем выше текущей цены

        # Обновляем график с новыми ордерами
        self.graph.update_orders(self.order_manager.get_orders())

    def stop(self):
        self.stop_simulation = True
        self.timer.stop()

    def set_grid_settings(self, settings):
        self.grid_size = settings['grid_size']
        self.volatility = settings['volatility']

    def update(self):
        if not self.stop_simulation:
            new_price = max(0, self.current_price + np.random.uniform(-self.volatility, self.volatility))
            self.graph.update_graph(new_price)
            self.order_manager.check_orders(new_price)
            self.current_price = new_price

    def mouse_moved(self, evt):
        pos = evt
        if self.graph.graphWidget.sceneBoundingRect().contains(pos):
            mouse_point = self.graph.graphWidget.plotItem.vb.mapSceneToView(pos)
            cursor_position = mouse_point.y()
            if QtGui.QGuiApplication.mouseButtons() == QtCore.Qt.LeftButton:
                self.current_price = max(0, cursor_position + np.random.uniform(-self.volatility, self.volatility))

    def key_pressed(self, event):
        if event.key() == QtCore.Qt.Key_Up:  # Проверяем, нажата ли клавиша вверх
            # Устанавливаем новую цену с небольшим увеличением
            self.current_price += self.volatility  # Добавляем волатильность к текущей цене для изменения
            self.graph.update_graph(self.current_price)  # Обновляем график с новой ценой

            # Не забываем обновить ордера
            self.order_manager.check_orders(self.current_price)

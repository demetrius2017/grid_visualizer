import sys
from PyQt5 import QtGui, QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np

# Настройка основного окна
app = QtWidgets.QApplication([])
win = pg.GraphicsLayoutWidget(show=True, title="Real-time market price simulation")
win.resize(1000, 600)
win.setWindowTitle('Market Price Simulation')

# Настройка графика
plot = win.addPlot(title="Market Price")
curve = plot.plot(pen='y')
plot.setYRange(0, 1)  # Диапазон значений Y
plot.showGrid(x=True, y=True)

# Параметры для генерации данных
candles = []
current_price = 0.5
candles.append(current_price)
volatility = .005
stop_simulation = False

def update():
    global current_price
    if not stop_simulation:
        new_price = max(0, current_price + np.random.uniform(-volatility, volatility))
        candles.append(new_price)
        if len(candles) > 100:
            candles.pop(0)
        curve.setData(candles)

def mouseMoved(evt):
    global current_price
    pos = evt[0]  # получение координат мыши
    if plot.sceneBoundingRect().contains(pos):
        mouse_point = plot.vb.mapSceneToView(pos)
        cursor_position = mouse_point.y()
        # Установка границ движения цены относительно курсора
        current_price = max(0, cursor_position + np.random.uniform(-volatility, volatility))

# Соединение сигналов
proxy = pg.SignalProxy(plot.scene().sigMouseMoved, rateLimit=60, slot=mouseMoved)
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(50)

# Запуск приложения
sys.exit(app.exec_())

from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

class MarketGraph(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Market Price Simulation")
        self.setGeometry(100, 100, 1000, 600)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.graphWidget = pg.PlotWidget()
        layout.addWidget(self.graphWidget)

        self.curve = self.graphWidget.plot(pen='y')
        self.graphWidget.setYRange(0, 1)
        self.graphWidget.showGrid(x=True, y=True)

        self.data = []

    def update_graph(self, new_price):
        self.data.append(new_price)
        if len(self.data) > 100:
            self.data.pop(0)
        self.curve.setData(self.data)

import sys
from PyQt5 import QtWidgets
from graph import MarketGraph
from trading import TradingSimulator
from menu import MainWindow


def main():
    app = QtWidgets.QApplication([])

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

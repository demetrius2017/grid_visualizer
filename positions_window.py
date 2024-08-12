from PyQt5 import QtWidgets, QtCore

class PositionsWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Positions")
        self.setGeometry(100, 100, 800, 400)  # Увеличили ширину окна

        layout = QtWidgets.QVBoxLayout()

        self.open_positions_table = QtWidgets.QTableWidget()
        self.open_positions_table.setColumnCount(6)  # Добавили колонку для комиссии
        self.open_positions_table.setHorizontalHeaderLabels(["Type", "Entry Price", "Volume", "Floating Profit", "Current Price", "Commission"])
        layout.addWidget(QtWidgets.QLabel("Open Positions"))
        layout.addWidget(self.open_positions_table)

        self.closed_positions_table = QtWidgets.QTableWidget()
        self.closed_positions_table.setColumnCount(6)  # Добавили колонку для комиссии
        self.closed_positions_table.setHorizontalHeaderLabels(["Type", "Entry Price", "Exit Price", "Volume", "Profit", "Commission"])
        layout.addWidget(QtWidgets.QLabel("Closed Positions"))
        layout.addWidget(self.closed_positions_table)

        self.setLayout(layout)

    def update_positions(self, open_positions, closed_positions, current_price):
        self.open_positions_table.setRowCount(len(open_positions))
        for i, position in enumerate(open_positions):
            self.open_positions_table.setItem(i, 0, QtWidgets.QTableWidgetItem(position.order_type))
            self.open_positions_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{position.entry_price:.8f}"))
            self.open_positions_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{position.volume:.8f}"))
            self.open_positions_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{position.floating_profit:.8f}"))
            self.open_positions_table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{current_price:.8f}"))
            commission = position.volume * position.entry_price * 0.00016  # Расчет комиссии (0.016%)
            self.open_positions_table.setItem(i, 5, QtWidgets.QTableWidgetItem(f"{commission:.8f}"))

        self.closed_positions_table.setRowCount(len(closed_positions))
        for i, position in enumerate(closed_positions):
            self.closed_positions_table.setItem(i, 0, QtWidgets.QTableWidgetItem(position.order_type))
            self.closed_positions_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{position.entry_price:.8f}"))
            self.closed_positions_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{position.exit_price:.8f}"))
            self.closed_positions_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{position.volume:.8f}"))
            self.closed_positions_table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{position.profit:.8f}"))
            commission = position.volume * position.entry_price * 0.00016  # Расчет комиссии (0.016%)
            self.closed_positions_table.setItem(i, 5, QtWidgets.QTableWidgetItem(f"{commission:.8f}"))

    def clear(self):
        self.open_positions_table.setRowCount(0)
        self.closed_positions_table.setRowCount(0)
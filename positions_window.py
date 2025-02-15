from PyQt5 import QtWidgets, QtCore


class PositionsWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Positions")
        self.setGeometry(100, 100, 800, 600)

        layout = QtWidgets.QVBoxLayout()
        self.tab_widget = QtWidgets.QTabWidget()

        # Вкладка позиций
        positions_tab = QtWidgets.QWidget()
        positions_layout = QtWidgets.QVBoxLayout()

        self.open_positions_table = QtWidgets.QTableWidget()
        self.open_positions_table.setColumnCount(6)
        self.open_positions_table.setHorizontalHeaderLabels(
            [
                "Type",
                "Entry Price",
                "Volume",
                "Floating Profit",
                "Current Price",
                "Commission",
            ]
        )
        positions_layout.addWidget(QtWidgets.QLabel("Open Positions"))
        positions_layout.addWidget(self.open_positions_table)

        self.closed_positions_table = QtWidgets.QTableWidget()
        self.closed_positions_table.setColumnCount(6)
        self.closed_positions_table.setHorizontalHeaderLabels(
            ["Type", "Entry Price", "Exit Price", "Volume", "Profit", "Commission"]
        )
        positions_layout.addWidget(QtWidgets.QLabel("Closed Positions"))
        positions_layout.addWidget(self.closed_positions_table)

        positions_tab.setLayout(positions_layout)

        # Вкладка активных опционов
        options_tab = QtWidgets.QWidget()
        options_layout = QtWidgets.QVBoxLayout()

        self.hedge_table = QtWidgets.QTableWidget()
        self.hedge_table.setColumnCount(4)
        self.hedge_table.setHorizontalHeaderLabels(
            ["Option Type", "Strike", "Premium", "Current Value"]
        )
        options_layout.addWidget(QtWidgets.QLabel("Active Hedge Positions"))
        options_layout.addWidget(self.hedge_table)

        options_tab.setLayout(options_layout)

        # Вкладка истории опционов
        options_history_tab = QtWidgets.QWidget()
        options_history_layout = QtWidgets.QVBoxLayout()

        self.options_history_table = QtWidgets.QTableWidget()
        self.options_history_table.setColumnCount(6)
        self.options_history_table.setHorizontalHeaderLabels(
            [
                "Option Type",
                "Strike",
                "Premium Paid",
                "Trigger Price",
                "Payout",
                "Net Profit",
            ]
        )
        options_history_layout.addWidget(QtWidgets.QLabel("Options History"))
        options_history_layout.addWidget(self.options_history_table)

        self.options_stats_label = QtWidgets.QLabel()
        options_history_layout.addWidget(self.options_stats_label)

        options_history_tab.setLayout(options_history_layout)

        # Добавляем вкладки
        self.tab_widget.addTab(positions_tab, "Positions")
        self.tab_widget.addTab(options_tab, "Active Options")
        self.tab_widget.addTab(options_history_tab, "Options History")

        # Добавляем сводку
        self.summary_label = QtWidgets.QLabel()
        layout.addWidget(self.tab_widget)
        layout.addWidget(self.summary_label)

        self.setLayout(layout)

    def update_positions(
        self,
        open_positions,
        closed_positions,
        current_price,
        active_options=None,
        options_history=None,
    ):
        # Обновление открытых позиций
        self.open_positions_table.setRowCount(len(open_positions))
        for i, position in enumerate(open_positions):
            self.open_positions_table.setItem(
                i, 0, QtWidgets.QTableWidgetItem(position.order_type)
            )
            self.open_positions_table.setItem(
                i, 1, QtWidgets.QTableWidgetItem(f"{position.entry_price:.8f}")
            )
            self.open_positions_table.setItem(
                i, 2, QtWidgets.QTableWidgetItem(f"{position.volume:.8f}")
            )
            self.open_positions_table.setItem(
                i, 3, QtWidgets.QTableWidgetItem(f"{position.floating_profit:.8f}")
            )
            self.open_positions_table.setItem(
                i, 4, QtWidgets.QTableWidgetItem(f"{current_price:.8f}")
            )
            self.open_positions_table.setItem(
                i, 5, QtWidgets.QTableWidgetItem(f"{position.commission:.8f}")
            )

        # Обновление закрытых позиций
        self.closed_positions_table.setRowCount(len(closed_positions))
        for i, position in enumerate(closed_positions):
            self.closed_positions_table.setItem(
                i, 0, QtWidgets.QTableWidgetItem(position.order_type)
            )
            self.closed_positions_table.setItem(
                i, 1, QtWidgets.QTableWidgetItem(f"{position.entry_price:.8f}")
            )
            self.closed_positions_table.setItem(
                i, 2, QtWidgets.QTableWidgetItem(f"{position.exit_price:.8f}")
            )
            self.closed_positions_table.setItem(
                i, 3, QtWidgets.QTableWidgetItem(f"{position.volume:.8f}")
            )
            self.closed_positions_table.setItem(
                i, 4, QtWidgets.QTableWidgetItem(f"{position.profit:.8f}")
            )
            self.closed_positions_table.setItem(
                i, 5, QtWidgets.QTableWidgetItem(f"{position.commission:.8f}")
            )

        # Обновление активных опционов
        if active_options:
            self.hedge_table.setRowCount(
                len(active_options) * 2
            )  # 2 опциона на позицию
            row = 0
            for position in active_options:
                # Put option
                self.hedge_table.setItem(row, 0, QtWidgets.QTableWidgetItem("Put"))
                self.hedge_table.setItem(
                    row,
                    1,
                    QtWidgets.QTableWidgetItem(f"{position['put']['strike']:.8f}"),
                )
                self.hedge_table.setItem(
                    row,
                    2,
                    QtWidgets.QTableWidgetItem(f"{position['put']['premium']:.8f}"),
                )
                put_value = max(0, position["put"]["strike"] - current_price)
                self.hedge_table.setItem(
                    row, 3, QtWidgets.QTableWidgetItem(f"{put_value:.8f}")
                )

                # Call option
                row += 1
                self.hedge_table.setItem(row, 0, QtWidgets.QTableWidgetItem("Call"))
                self.hedge_table.setItem(
                    row,
                    1,
                    QtWidgets.QTableWidgetItem(f"{position['call']['strike']:.8f}"),
                )
                self.hedge_table.setItem(
                    row,
                    2,
                    QtWidgets.QTableWidgetItem(f"{position['call']['premium']:.8f}"),
                )
                call_value = max(0, current_price - position["call"]["strike"])
                self.hedge_table.setItem(
                    row, 3, QtWidgets.QTableWidgetItem(f"{call_value:.8f}")
                )
                row += 1
        else:
            self.hedge_table.setRowCount(0)

        # Обновление истории опционов
        if options_history:
            self.options_history_table.setRowCount(len(options_history))
            total_premium_paid = 0
            total_payout = 0

            for i, option in enumerate(options_history):
                # Put option
                put_payout = max(
                    0, option["put"]["strike"] - option.get("trigger_price", 0)
                )
                put_premium = option["put"]["premium"]

                # Call option
                call_payout = max(
                    0, option.get("trigger_price", 0) - option["call"]["strike"]
                )
                call_premium = option["call"]["premium"]

                # Записываем тот опцион, который сработал
                if put_payout > 0:
                    option_type = "Put"
                    strike = option["put"]["strike"]
                    premium = put_premium
                    payout = put_payout
                else:
                    option_type = "Call"
                    strike = option["call"]["strike"]
                    premium = call_premium
                    payout = call_payout

                total_premium_paid += put_premium + call_premium
                total_payout += put_payout + call_payout

                self.options_history_table.setItem(
                    i, 0, QtWidgets.QTableWidgetItem(option_type)
                )
                self.options_history_table.setItem(
                    i, 1, QtWidgets.QTableWidgetItem(f"{strike:.8f}")
                )
                self.options_history_table.setItem(
                    i, 2, QtWidgets.QTableWidgetItem(f"{premium:.8f}")
                )
                self.options_history_table.setItem(
                    i,
                    3,
                    QtWidgets.QTableWidgetItem(f"{option.get('trigger_price', 0):.8f}"),
                )
                self.options_history_table.setItem(
                    i, 4, QtWidgets.QTableWidgetItem(f"{payout:.8f}")
                )
                self.options_history_table.setItem(
                    i, 5, QtWidgets.QTableWidgetItem(f"{payout - premium:.8f}")
                )

            # Обновляем статистику по опционам
            net_result = total_payout - total_premium_paid
            self.options_stats_label.setText(
                f"Total Premiums Paid: {total_premium_paid:.8f}\n"
                f"Total Payouts: {total_payout:.8f}\n"
                f"Net Result: {net_result:.8f}"
            )

        # Обновление общей сводки
        total_profit = sum(position.profit for position in closed_positions)
        total_commission = sum(position.commission for position in closed_positions)
        net_profit = total_profit - total_commission

        self.summary_label.setText(
            f"Total Profit (including commission): {net_profit:.8f}\n"
            f"Gross Profit: {total_profit:.8f}\n"
            f"Total Commission: {total_commission:.8f}"
        )

    def clear(self):
        self.open_positions_table.setRowCount(0)
        self.closed_positions_table.setRowCount(0)
        self.hedge_table.setRowCount(0)
        self.options_history_table.setRowCount(0)
        self.summary_label.setText("")
        self.options_stats_label.setText("")

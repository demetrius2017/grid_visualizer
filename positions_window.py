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
        self.hedge_table.setHorizontalHeaderLabels(["Option Type", "Strike", "Premium", "Current Value"])
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

        # Новая вкладка для информации об адаптивной сетке
        adaptive_grid_tab = QtWidgets.QWidget()
        adaptive_grid_layout = QtWidgets.QVBoxLayout()

        # Группа информации о скорости сделок
        trade_speed_group = QtWidgets.QGroupBox("Скорость сделок")
        trade_speed_layout = QtWidgets.QFormLayout()
        
        self.buy_speed_label = QtWidgets.QLabel("0.0")
        self.sell_speed_label = QtWidgets.QLabel("0.0")
        self.buy_interval_label = QtWidgets.QLabel("0.0")
        self.sell_interval_label = QtWidgets.QLabel("0.0")
        self.buy_history_label = QtWidgets.QLabel("0")
        self.sell_history_label = QtWidgets.QLabel("0")
        
        trade_speed_layout.addRow("Скорость BUY (сделок/тик):", self.buy_speed_label)
        trade_speed_layout.addRow("Скорость SELL (сделок/тик):", self.sell_speed_label)
        trade_speed_layout.addRow("Средний интервал BUY (тики):", self.buy_interval_label)
        trade_speed_layout.addRow("Средний интервал SELL (тики):", self.sell_interval_label)
        trade_speed_layout.addRow("Размер истории BUY:", self.buy_history_label)
        trade_speed_layout.addRow("Размер истории SELL:", self.sell_history_label)
        
        trade_speed_group.setLayout(trade_speed_layout)
        adaptive_grid_layout.addWidget(trade_speed_group)
        
        # Группа информации о шаге сетки
        grid_step_group = QtWidgets.QGroupBox("Адаптивный шаг сетки")
        grid_step_layout = QtWidgets.QFormLayout()
        
        self.base_grid_step_label = QtWidgets.QLabel("0.0%")
        self.current_buy_step_label = QtWidgets.QLabel("0.0%")
        self.current_sell_step_label = QtWidgets.QLabel("0.0%")
        self.min_grid_step_label = QtWidgets.QLabel("0.0%")
        self.buy_step_multiplier_label = QtWidgets.QLabel("1.0")
        self.sell_step_multiplier_label = QtWidgets.QLabel("1.0")
        
        grid_step_layout.addRow("Базовый шаг сетки:", self.base_grid_step_label)
        grid_step_layout.addRow("Текущий шаг BUY:", self.current_buy_step_label)
        grid_step_layout.addRow("Текущий шаг SELL:", self.current_sell_step_label)
        grid_step_layout.addRow("Минимальный шаг:", self.min_grid_step_label)
        grid_step_layout.addRow("Множитель BUY:", self.buy_step_multiplier_label)
        grid_step_layout.addRow("Множитель SELL:", self.sell_step_multiplier_label)
        
        grid_step_group.setLayout(grid_step_layout)
        adaptive_grid_layout.addWidget(grid_step_group)
        
        # Счетчики последовательных сделок
        consecutive_group = QtWidgets.QGroupBox("Последовательные сделки")
        consecutive_layout = QtWidgets.QFormLayout()
        
        self.consecutive_buys_label = QtWidgets.QLabel("0")
        self.consecutive_sells_label = QtWidgets.QLabel("0")
        
        consecutive_layout.addRow("Последовательных BUY:", self.consecutive_buys_label)
        consecutive_layout.addRow("Последовательных SELL:", self.consecutive_sells_label)
        
        consecutive_group.setLayout(consecutive_layout)
        adaptive_grid_layout.addWidget(consecutive_group)
        
        adaptive_grid_tab.setLayout(adaptive_grid_layout)

        # Добавляем вкладки
        self.tab_widget.addTab(positions_tab, "Positions")
        self.tab_widget.addTab(options_tab, "Active Options")
        self.tab_widget.addTab(options_history_tab, "Options History")
        self.tab_widget.addTab(adaptive_grid_tab, "Адаптивная сетка")

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
        balance=None,
        free_margin=None,
        floating_profit=None,
        open_orders_count=None,
        total_trades_count=None,
        # Добавляем новые параметры для адаптивной сетки
        trade_speed_stats=None,
        grid_steps=None
    ):
        # Улучшенное логирование для математической отладки позиций
        import logging
        logger = logging.getLogger("grid_visualizer")
        
        # Логируем количество и типы позиций для математической проверки
        buy_positions = [p for p in open_positions if p.order_type == "buy"]
        sell_positions = [p for p in open_positions if p.order_type == "sell"]
        
        logger.info(f"[GRID_MATH] Open positions: {len(open_positions)} (Buy: {len(buy_positions)}, Sell: {len(sell_positions)})")
        
        # Проверка на одновременно открытые противоположные позиции - математический дисбаланс
        if buy_positions and sell_positions:
            buy_volume = sum(p.volume for p in buy_positions)
            sell_volume = sum(p.volume for p in sell_positions)
            logger.warning(f"[GRID_MATH] Simultaneous open positions detected! Buy vol: {buy_volume:.8f}, Sell vol: {sell_volume:.8f}, Diff: {buy_volume-sell_volume:.8f}")
            
            # Вывод подробной информации о пересекающихся позициях для отладки
            for bp in buy_positions:
                logger.debug(f"[GRID_MATH] BUY: entry={bp.entry_price:.8f}, vol={bp.volume:.8f}, floating={bp.floating_profit:.8f}")
            for sp in sell_positions:
                logger.debug(f"[GRID_MATH] SELL: entry={sp.entry_price:.8f}, vol={sp.volume:.8f}, floating={sp.floating_profit:.8f}")
        
        # Обновление открытых позиций
        self.open_positions_table.setRowCount(len(open_positions))
        
        # Рассчитываем сумму floating profit из открытых позиций
        total_positions_floating_profit = 0.0
        
        for i, position in enumerate(open_positions):
            self.open_positions_table.setItem(i, 0, QtWidgets.QTableWidgetItem(position.order_type))
            self.open_positions_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{position.entry_price:.8f}"))
            self.open_positions_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{position.volume:.8f}"))
            self.open_positions_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{position.floating_profit:.8f}"))
            self.open_positions_table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{current_price:.8f}"))
            self.open_positions_table.setItem(i, 5, QtWidgets.QTableWidgetItem(f"{position.commission:.8f}"))
            
            # Суммируем floating profit из позиций
            total_positions_floating_profit += position.floating_profit

        # Обновление закрытых позиций
        self.closed_positions_table.setRowCount(len(closed_positions))
        for i, position in enumerate(closed_positions):
            self.closed_positions_table.setItem(i, 0, QtWidgets.QTableWidgetItem(position.order_type))
            self.closed_positions_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{position.entry_price:.8f}"))
            self.closed_positions_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{position.exit_price:.8f}"))
            self.closed_positions_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{position.volume:.8f}"))
            self.closed_positions_table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{position.profit:.8f}"))
            self.closed_positions_table.setItem(i, 5, QtWidgets.QTableWidgetItem(f"{position.commission:.8f}"))

        # Обновление активных опционов
        if active_options:
            self.hedge_table.setRowCount(len(active_options))
            for i, option in enumerate(active_options):
                self.hedge_table.setItem(i, 0, QtWidgets.QTableWidgetItem(option["type"].capitalize()))
                self.hedge_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{option['strike']:.8f}"))
                self.hedge_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{option['premium']:.8f}"))

                # Расчет текущей стоимости опциона
                if option["type"] == "put":
                    current_value = max(0, option["strike"] - current_price)
                else:  # call
                    current_value = max(0, current_price - option["strike"])

                self.hedge_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{current_value:.8f}"))
        else:
            self.hedge_table.setRowCount(0)

        # Обновление истории опционов
        if options_history:
            self.options_history_table.setRowCount(len(options_history))
            total_premium_paid = 0
            total_payout = 0

            for i, option in enumerate(options_history):
                option_type = option["type"].capitalize()
                strike = option["strike"]
                trigger_price = option["trigger_price"]
                payout = option["payout"]

                # Премия опциона теперь должна предоставляться в истории
                premium = option.get("premium", 0)
                total_premium_paid += premium
                total_payout += payout

                self.options_history_table.setItem(i, 0, QtWidgets.QTableWidgetItem(option_type))
                self.options_history_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{strike:.8f}"))
                self.options_history_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{premium:.8f}"))
                self.options_history_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{trigger_price:.8f}"))
                self.options_history_table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{payout:.8f}"))
                self.options_history_table.setItem(i, 5, QtWidgets.QTableWidgetItem(f"{payout - premium:.8f}"))

            # Обновляем статистику по опционам
            net_result = total_payout - total_premium_paid
            self.options_stats_label.setText(
                f"Total Premiums Paid: {total_premium_paid:.8f}\n"
                f"Total Payouts: {total_payout:.8f}\n"
                f"Net Result: {net_result:.8f}"
            )
        
        # Обновление информации об адаптивной сетке
        if trade_speed_stats:
            # Обновляем скорость сделок
            self.buy_speed_label.setText(f"{trade_speed_stats.get('buy_speed', 0.0):.6f}")
            self.sell_speed_label.setText(f"{trade_speed_stats.get('sell_speed', 0.0):.6f}")
            self.buy_interval_label.setText(f"{trade_speed_stats.get('buy_avg_interval', 0.0):.1f}")
            self.sell_interval_label.setText(f"{trade_speed_stats.get('sell_avg_interval', 0.0):.1f}")
            self.buy_history_label.setText(f"{trade_speed_stats.get('buy_history_size', 0)}")
            self.sell_history_label.setText(f"{trade_speed_stats.get('sell_history_size', 0)}")
            self.consecutive_buys_label.setText(f"{trade_speed_stats.get('buy_consecutive', 0)}")
            self.consecutive_sells_label.setText(f"{trade_speed_stats.get('sell_consecutive', 0)}")
        
        # Обновление информации о шаге сетки
        if grid_steps:
            base_step = grid_steps.get('base_step', 0.0)
            buy_step = grid_steps.get('buy_step', 0.0)
            sell_step = grid_steps.get('sell_step', 0.0)
            min_step = grid_steps.get('min_step', 0.0)
            
            # Рассчитываем множители относительно базового шага
            buy_multiplier = buy_step / base_step if base_step > 0 else 1.0
            sell_multiplier = sell_step / base_step if base_step > 0 else 1.0
            
            # Обновляем метки
            self.base_grid_step_label.setText(f"{base_step:.4f}%")
            self.current_buy_step_label.setText(f"{buy_step:.4f}%")
            self.current_sell_step_label.setText(f"{sell_step:.4f}%")
            self.min_grid_step_label.setText(f"{min_step:.4f}%")
            self.buy_step_multiplier_label.setText(f"{buy_multiplier:.2f}x")
            self.sell_step_multiplier_label.setText(f"{sell_multiplier:.2f}x")
            
        # Обновление общей сводки с информацией о марже
        total_profit = sum(position.profit for position in closed_positions)
        total_commission = sum(position.commission for position in closed_positions)
        
        # Используем переданное значение floating_profit если оно есть, 
        # иначе используем сумму из открытых позиций
        if floating_profit is None:
            floating_profit = total_positions_floating_profit
            
        # Проверка на несоответствие суммы по позициям и общей суммы
        if abs(floating_profit - total_positions_floating_profit) > 0.000001:
            print(f"WARNING: Floating profit mismatch: Positions sum={total_positions_floating_profit:.8f}, Total={floating_profit:.8f}")
            # Выводим предупреждение, но используем общую сумму из OrderManager
            
        net_profit = total_profit - total_commission

        # Создаем более заметный блок информации с помощью разделителей
        summary_text = []
        summary_text.append("=" * 40)
        summary_text.append("ТОРГОВАЯ СТАТИСТИКА")
        summary_text.append("=" * 40)
        
        # Количество открытых ордеров и общее количество сделок
        if open_orders_count is not None:
            summary_text.append(f"Открытых ордеров: {open_orders_count}")
        else:
            summary_text.append(f"Открытых ордеров: {len(open_positions)}")
            
        # Добавляем явное отображение количества открытых позиций
        summary_text.append(f"Открытых позиций: {len(open_positions)}")
            
        if total_trades_count is not None:
            summary_text.append(f"Общее количество сделок: {total_trades_count}")
        else:
            summary_text.append(f"Закрытых сделок: {len(closed_positions)}")
            
        summary_text.append("-" * 40)
        
        # Основная информация о прибыли и убытках
        summary_text.append(f"Чистая прибыль (с учетом комиссий): {net_profit:.8f}")
        summary_text.append(f"Валовая прибыль: {total_profit:.8f}")
        summary_text.append(f"Плавающая прибыль/убыток: {floating_profit:.8f}")
        summary_text.append(f"Общая комиссия: {total_commission:.8f}")
        
        # Добавляем разделитель
        summary_text.append("-" * 40)
        
        # Информация о балансе и марже (важные данные!)
        # Выделяем эту информацию, чтобы она была хорошо заметна
        if balance is not None:
            summary_text.append(f"БАЛАНС: {balance:.8f}")
        else:
            summary_text.append("БАЛАНС: Нет данных")
            
        if free_margin is not None:
            summary_text.append(f"СВОБОДНАЯ МАРЖА: {free_margin:.8f}")
        else:
            summary_text.append("СВОБОДНАЯ МАРЖА: Нет данных")
            
        # Добавляем информацию о текущем шаге сетки
        if grid_steps:
            summary_text.append("-" * 40)
            summary_text.append(f"АДАПТИВНЫЙ ШАГ: BUY={grid_steps.get('buy_step', 0.0):.4f}%, SELL={grid_steps.get('sell_step', 0.0):.4f}%")
        
        # Заключительный разделитель
        summary_text.append("=" * 40)

        # Обновляем текст сводки
        self.summary_label.setText("\n".join(summary_text))

    def clear(self):
        self.open_positions_table.setRowCount(0)
        self.closed_positions_table.setRowCount(0)
        self.hedge_table.setRowCount(0)
        self.options_history_table.setRowCount(0)
        self.summary_label.setText("")
        self.options_stats_label.setText("")
        
        # Очищаем информацию об адаптивной сетке
        self.buy_speed_label.setText("0.0")
        self.sell_speed_label.setText("0.0")
        self.buy_interval_label.setText("0.0")
        self.sell_interval_label.setText("0.0")
        self.buy_history_label.setText("0")
        self.sell_history_label.setText("0")
        self.consecutive_buys_label.setText("0")
        self.consecutive_sells_label.setText("0")
        self.base_grid_step_label.setText("0.0%")
        self.current_buy_step_label.setText("0.0%")
        self.current_sell_step_label.setText("0.0%")
        self.min_grid_step_label.setText("0.0%")
        self.buy_step_multiplier_label.setText("1.0")
        self.sell_step_multiplier_label.setText("1.0")

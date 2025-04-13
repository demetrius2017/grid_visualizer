import sys
import cProfile
import pstats
import logging
import time
import traceback
import argparse
import os
from logging.handlers import RotatingFileHandler
from pstats import SortKey
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread, pyqtSignal
from graph import MarketGraph
from trading import TradingSimulator
from menu import MainWindow

# Глобальные флаги для отслеживания состояния приложения
graph_active = True
orders_shown = False
last_graph_update = 0


def setup_logging():
    """
    Настраивает логирование с ротацией файлов и обработкой ошибок
    """
    log_dir = os.path.dirname(os.path.abspath(__file__))
    app_log_path = os.path.join(log_dir, "app_debug.log")
    detailed_log_path = os.path.join(log_dir, "detailed_debug.log")

    # Безопасная очистка лог-файлов перед началом работы
    try:
        # Проверяем наличие и доступность файлов
        for log_file in [app_log_path, detailed_log_path]:
            if os.path.exists(log_file):
                try:
                    with open(log_file, "w") as f:
                        f.write("")  # Очищаем файл
                except (IOError, PermissionError) as e:
                    print(f"Предупреждение: не удалось очистить лог-файл {log_file}: {e}")
            else:
                # Создаем директорию, если не существует
                os.makedirs(os.path.dirname(log_file), exist_ok=True)

    except Exception as e:
        print(f"Ошибка при подготовке лог-файлов: {e}")
        # Продолжаем выполнение, логи будут записываться с добавлением

    # Настраиваем корневой логгер
    try:
        # Создаем ротирующие обработчики для файлов логов
        app_handler = RotatingFileHandler(app_log_path, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
        app_handler.setLevel(logging.DEBUG)
        app_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

        detailed_handler = RotatingFileHandler(
            detailed_log_path, maxBytes=20 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        detailed_handler.setLevel(logging.DEBUG)
        detailed_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - [%(levelname)s] - %(message)s - %(filename)s:%(lineno)d")
        )

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # Для консоли используем INFO уровень
        console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

        # Настраиваем корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Удаляем существующие обработчики, чтобы избежать дублирования
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Добавляем новые обработчики
        root_logger.addHandler(app_handler)
        root_logger.addHandler(console_handler)

        # Создаем специальный логгер для приложения
        logger = logging.getLogger("grid_visualizer")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(detailed_handler)

        # Настраиваем перехват необработанных исключений
        def log_unhandled_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                # Не перехватываем KeyboardInterrupt
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return

            logger.critical("Необработанное исключение:", exc_info=(exc_type, exc_value, exc_traceback))

        sys.excepthook = log_unhandled_exception

        logger.info("Логирование настроено успешно")
        return logger

    except Exception as e:
        print(f"Критическая ошибка при настройке логирования: {e}")
        # Аварийная настройка базового логирования
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler()]
        )
        logger = logging.getLogger("grid_visualizer")
        logger.error(f"Не удалось настроить расширенное логирование: {e}")
        return logger


# Функция для запуска в безголовом режиме (без GUI)
def run_headless_simulation(csv_file=None, max_positions=30, stop_after_positions=True, timeout=300, output_path=None):
    """
    Запускает симуляцию в безголовом режиме без графического интерфейса

    :param csv_file: путь к CSV файлу с данными (если None, используется случайная генерация)
    :param max_positions: максимальное количество позиций для обработки
    :param stop_after_positions: если True, останавливается после достижения max_positions
    :param timeout: тайм-аут в секундах для безголового режима
    :param output_path: путь для сохранения отчета о симуляции
    """
    logger = setup_logging()
    logger.info("[HEADLESS] Запуск симуляции в безголовом режиме")

    # Инициализация QApplication для работы событийного цикла
    app = QtWidgets.QApplication([])

    # Создаем объект графика (без отображения)
    market_graph = MarketGraph()

    # Создаем симулятор с графиком
    simulator = TradingSimulator(
        market_graph,
        initial_balance=100000,
        grid_size=20,
        ema_period=50,
        min_grid_coverage=0.10,
        min_orders=5,
        max_orders=20,
    )

    # Устанавливаем CSV файл, если он указан
    if csv_file:
        logger.info(f"[HEADLESS] Загрузка данных из файла: {csv_file}")
        simulator.set_csv_file(csv_file)
    else:
        logger.info("[HEADLESS] Используется случайная генерация цен")
        simulator.simulation_mode = "random"

    # Включаем создание ордеров
    simulator.order_manager.orders_enabled = True
    simulator.order_manager.active = True
    simulator.order_manager.processing_enabled = True

    # Устанавливаем счетчик закрытых позиций
    closed_positions_count = 0

    # Сохраняем время начала для расчета скорости обработки
    start_time = time.time()

    # Переменные для отслеживания статистики
    max_profit = 0
    min_profit = 0
    profit_sum = 0
    position_count_by_levels = {}
    level_profits = {}

    # Устанавливаем таймер для регулярной проверки числа закрытых позиций
    check_timer = QtCore.QTimer()

    def check_positions():
        nonlocal closed_positions_count, max_profit, min_profit, profit_sum
        current_closed = len(simulator.order_manager.closed_positions)

        if current_closed > closed_positions_count:
            new_positions = current_closed - closed_positions_count
            logger.info(f"[HEADLESS] Новые закрытые позиции: +{new_positions}, всего: {current_closed}")

            # Анализируем новые закрытые позиции
            for i in range(closed_positions_count, current_closed):
                pos = simulator.order_manager.closed_positions[i]

                # Обновляем статистику
                if pos.profit > max_profit:
                    max_profit = pos.profit
                if pos.profit < min_profit or min_profit == 0:
                    min_profit = pos.profit
                profit_sum += pos.profit

                # Отслеживаем статистику по уровням
                level = pos.level if hasattr(pos, "level") else 0
                position_count_by_levels[level] = position_count_by_levels.get(level, 0) + 1
                level_profits[level] = level_profits.get(level, 0) + pos.profit

                # Логируем детали закрытой позиции
                logger.info(
                    f"[HEADLESS] Позиция {i+1}: {pos.order_type}, вход={pos.entry_price:.2f}, "
                    f"выход={pos.exit_price:.2f}, объем={pos.volume:.8f}, прибыль={pos.profit:.2f}, уровень={level}"
                )

            closed_positions_count = current_closed

            # Логируем состояние баланса и маржи
            balance = simulator.order_manager.get_balance()
            free_margin = simulator.order_manager.get_free_margin()
            floating_profit = simulator.order_manager.calculate_floating_profit(simulator.current_price)

            logger.info(
                f"[HEADLESS] Баланс: {balance:.2f}, Своб. маржа: {free_margin:.2f}, Плав. прибыль: {floating_profit:.2f}"
            )

            # Вычисляем и логируем скорость обработки позиций
            elapsed_time = time.time() - start_time
            positions_per_minute = (current_closed / elapsed_time) * 60
            logger.info(
                f"[HEADLESS] Скорость обработки: {positions_per_minute:.2f} позиций/мин, прошло времени: {elapsed_time:.2f}с"
            )

            # Логируем информацию о незакрытых позициях
            open_positions = simulator.order_manager.get_open_positions()
            open_buy = [p for p in open_positions if p.order_type == "buy"]
            open_sell = [p for p in open_positions if p.order_type == "sell"]

            logger.info(
                f"[HEADLESS] Открытые позиции: Buy: {len(open_buy)}, Sell: {len(open_sell)}, "
                f"Дифф: {len(open_buy) - len(open_sell)}"
            )

            # Логируем общую статистику
            if current_closed > 0:
                avg_profit = profit_sum / current_closed
                logger.info(
                    f"[HEADLESS] Статистика: Средняя прибыль: {avg_profit:.2f}, Макс.: {max_profit:.2f}, Мин.: {min_profit:.2f}"
                )

                # Статистика по уровням
                level_stats = []
                for level, count in sorted(position_count_by_levels.items()):
                    avg_level_profit = level_profits[level] / count
                    level_stats.append(f"L{level}:{count}шт({avg_level_profit:.2f})")

                logger.info(f"[HEADLESS] Статистика по уровням: {', '.join(level_stats)}")

        # Проверяем условие остановки
        if stop_after_positions and current_closed >= max_positions:
            logger.info(f"[HEADLESS] Достигнуто макс. число позиций ({max_positions}), завершение")

            # Печатаем финальный отчет перед завершением
            print_final_report()

            # Останавливаем таймеры и симуляцию
            check_timer.stop()
            simulator.stop()
            app.quit()

    def print_final_report():
        # Формируем финальный отчет о результатах симуляции
        total_closed = len(simulator.order_manager.closed_positions)
        final_balance = simulator.order_manager.get_balance()
        initial_balance = 100000  # Из параметров симулятора
        profit = final_balance - initial_balance

        logger.info("\n" + "=" * 50)
        logger.info(f"[HEADLESS] ИТОГОВЫЙ ОТЧЕТ")
        logger.info("=" * 50)
        logger.info(f"[HEADLESS] Всего закрыто позиций: {total_closed}")
        logger.info(f"[HEADLESS] Начальный баланс: {initial_balance:.2f}")
        logger.info(f"[HEADLESS] Конечный баланс: {final_balance:.2f}")
        logger.info(f"[HEADLESS] Итоговая прибыль: {profit:.2f} ({(profit/initial_balance)*100:.2f}%)")

        if total_closed > 0:
            logger.info(f"[HEADLESS] Средняя прибыль на позицию: {profit_sum/total_closed:.2f}")
            logger.info(f"[HEADLESS] Макс. прибыль: {max_profit:.2f}, Мин. прибыль: {min_profit:.2f}")

            # Статистика по типам позиций
            buy_positions = [p for p in simulator.order_manager.closed_positions if p.order_type == "buy"]
            sell_positions = [p for p in simulator.order_manager.closed_positions if p.order_type == "sell"]

            buy_profit = sum(p.profit for p in buy_positions)
            sell_profit = sum(p.profit for p in sell_positions)

            logger.info(f"[HEADLESS] Buy позиции: {len(buy_positions)}, прибыль: {buy_profit:.2f}")
            logger.info(f"[HEADLESS] Sell позиции: {len(sell_positions)}, прибыль: {sell_profit:.2f}")

            # Подробная статистика по уровням
            logger.info("[HEADLESS] Статистика по уровням:")
            for level, count in sorted(position_count_by_levels.items()):
                avg_level_profit = level_profits[level] / count
                pct = (count / total_closed) * 100
                logger.info(
                    f"[HEADLESS]   Уровень {level}: {count} позиций ({pct:.1f}%), "
                    f"прибыль: {level_profits[level]:.2f}, средняя: {avg_level_profit:.2f}"
                )
            
            # Расширенная статистика эффективности торговли
            if total_closed > 0:
                # Подсчитываем прибыльные и убыточные сделки
                profitable_positions = [p for p in simulator.order_manager.closed_positions if p.profit > 0]
                losing_positions = [p for p in simulator.order_manager.closed_positions if p.profit <= 0]
                
                profitable_count = len(profitable_positions)
                losing_count = len(losing_positions)
                win_rate = (profitable_count / total_closed) * 100
                
                # Средняя прибыль и убыток
                avg_win = sum(p.profit for p in profitable_positions) / profitable_count if profitable_count > 0 else 0
                avg_loss = sum(p.profit for p in losing_positions) / losing_count if losing_count > 0 else 0
                
                # Соотношение прибыль/риск
                risk_reward_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
                
                logger.info("=" * 40)
                logger.info("[HEADLESS] РАСШИРЕННАЯ СТАТИСТИКА ЭФФЕКТИВНОСТИ")
                logger.info(f"[HEADLESS] Прибыльные сделки: {profitable_count} ({win_rate:.1f}%)")
                logger.info(f"[HEADLESS] Убыточные сделки: {losing_count} ({100-win_rate:.1f}%)")
                logger.info(f"[HEADLESS] Средняя прибыль на выигрышную сделку: {avg_win:.2f}")
                logger.info(f"[HEADLESS] Средний убыток на проигрышную сделку: {avg_loss:.2f}")
                logger.info(f"[HEADLESS] Соотношение прибыль/риск: {risk_reward_ratio:.2f}")
                
                # Статистика по времени удержания позиций, если доступны временные метки
                if all(hasattr(p, 'exit_time') and hasattr(p, 'entry_time') for p in simulator.order_manager.closed_positions):
                    durations = [(p.exit_time - p.entry_time) for p in simulator.order_manager.closed_positions]
                    avg_duration = sum(durations) / len(durations) if durations else 0
                    max_duration = max(durations) if durations else 0
                    min_duration = min(durations) if durations else 0
                    
                    logger.info(f"[HEADLESS] Среднее время удержания позиций: {avg_duration:.2f} тиков")
                    logger.info(f"[HEADLESS] Максимальное время удержания: {max_duration:.2f} тиков")
                    logger.info(f"[HEADLESS] Минимальное время удержания: {min_duration:.2f} тиков")
                
                # Статистика по объемам позиций
                volumes = [p.volume for p in simulator.order_manager.closed_positions]
                avg_volume = sum(volumes) / len(volumes) if volumes else 0
                max_volume = max(volumes) if volumes else 0
                min_volume = min(volumes) if volumes else 0
                
                logger.info(f"[HEADLESS] Средний объем позиции: {avg_volume:.8f}")
                logger.info(f"[HEADLESS] Диапазон объемов: {min_volume:.8f} - {max_volume:.8f}")
                
                # Анализ комиссий и их влияния на прибыль
                total_commission = sum(p.commission for p in simulator.order_manager.closed_positions)
                avg_commission = total_commission / total_closed
                commission_percent = (total_commission / abs(profit_sum)) * 100 if profit_sum != 0 else 0
                
                logger.info(f"[HEADLESS] Общие комиссии: {total_commission:.2f}")
                logger.info(f"[HEADLESS] Средняя комиссия на сделку: {avg_commission:.2f}")
                logger.info(f"[HEADLESS] Комиссии в % от прибыли: {commission_percent:.2f}%")

        logger.info("=" * 50)

        # Информация о текущих открытых позициях
        open_positions = simulator.order_manager.get_open_positions()
        if open_positions:
            logger.info(f"[HEADLESS] Осталось {len(open_positions)} открытых позиций")
            for i, pos in enumerate(open_positions):
                floating = (
                    (simulator.current_price - pos.entry_price) * pos.volume
                    if pos.order_type == "buy"
                    else (pos.entry_price - simulator.current_price) * pos.volume
                )
                logger.info(
                    f"[HEADLESS]   {i+1}: {pos.order_type}, вход={pos.entry_price:.2f}, "
                    f"текущая цена={simulator.current_price:.2f}, объем={pos.volume:.8f}, "
                    f"плав. прибыль={floating:.2f}, уровень={getattr(pos, 'level', 0)}"
                )

    # Запускаем таймер проверки
    check_timer.timeout.connect(check_positions)
    check_timer.start(500)  # проверка каждые 500 мс

    # Запускаем таймер для мониторинга прогресса
    progress_timer = QtCore.QTimer()
    progress_timer.timeout.connect(
        lambda: logger.info(
            f"[HEADLESS] Прогресс: {len(simulator.order_manager.closed_positions)}/{max_positions} позиций, "
            f"прошло {(time.time() - start_time)/60:.1f} мин"
        )
    )
    progress_timer.start(30000)  # каждые 30 секунд

    # Запускаем таймер для принудительного завершения (защита от зависания)
    max_runtime_timer = QtCore.QTimer()
    max_runtime_timer.timeout.connect(
        lambda: (
            logger.warning("[HEADLESS] Достигнуто максимальное время работы, принудительное завершение"),
            print_final_report(),
            simulator.stop(),
            app.quit(),
        )
    )
    max_runtime_timer.setSingleShot(True)
    max_runtime_timer.start(timeout * 1000)  # тайм-аут в секундах

    # Запускаем симуляцию
    logger.info("[HEADLESS] Запуск симуляции")
    simulator.start()

    # Запускаем событийный цикл
    app.exec_()

    # Логируем итоговые результаты
    total_closed = len(simulator.order_manager.closed_positions)
    final_balance = simulator.order_manager.get_balance()

    logger.info(f"[HEADLESS] Симуляция завершена. Всего закрыто позиций: {total_closed}")
    logger.info(f"[HEADLESS] Итоговый баланс: {final_balance:.2f}")


def main():
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description="Grid Visualizer")
    parser.add_argument("--headless", action="store_true", help="Запуск в безголовом режиме без GUI")
    parser.add_argument("--csv", type=str, help="Путь к CSV файлу с данными")
    parser.add_argument("--max-positions", type=int, default=30, help="Максимальное количество позиций для обработки")
    parser.add_argument("--profile", action="store_true", help="Запуск с профилированием")
    parser.add_argument(
        "--no-stop", action="store_true", help="Не останавливать симуляцию после достижения макс. позиций"
    )
    parser.add_argument(
        "--timeout", type=int, default=300, help="Тайм-аут в секундах для безголового режима (по умолчанию 300)"
    )
    parser.add_argument("--output", type=str, help="Путь для сохранения отчета о симуляции")

    args = parser.parse_args()

    # Запуск в безголовом режиме, если указан соответствующий аргумент
    if args.headless:
        # Настраиваем параметры для безголового режима
        stop_after_positions = not args.no_stop

        # Запускаем симуляцию с расширенными параметрами
        run_headless_simulation(
            csv_file=args.csv,
            max_positions=args.max_positions,
            stop_after_positions=stop_after_positions,
            timeout=args.timeout,
            output_path=args.output,
        )
        return

    # Запуск с профилированием, если указан соответствующий аргумент
    if args.profile:
        profile_main()
        return

    # Обычный запуск с GUI
    logger = setup_logging()
    logger.info("Запуск приложения")
    start_time = time.time()

    app = QtWidgets.QApplication([])
    app.setStyle("Fusion")  # Используем Fusion стиль для лучшей производительности

    # Отключаем сглаживание для повышения производительности
    app.setAttribute(QtCore.Qt.AA_DisableHighDpiScaling, True)
    app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, False)

    main_window = MainWindow()
    logger.info("Главное окно создано")

    # Явно отключаем обработку событий до инициализации
    main_window.events_enabled = False
    if hasattr(main_window, "simulator"):
        if main_window.simulator:
            # Явно отключаем активность симулятора до старта
            main_window.simulator.stop_simulation = True
            main_window.simulator.order_manager.active = False
            main_window.simulator.order_manager.processing_enabled = False
            logger.info("Явно отключена активность симулятора до старта")

    # Отложенное обновление UI после инициализации
    QtCore.QTimer.singleShot(0, lambda: update_ui_safely(main_window, logger))

    # Создаем монитор состояния графика
    graph_monitor = GraphMonitor(main_window, logger)

    # Устанавливаем обработчик активации для правильного запуска симуляции
    install_start_simulation_monitor(main_window, logger, start_time)

    # Устанавливаем обработчик исключений Qt
    sys._excepthook = sys.excepthook

    def exception_hook(exctype, value, traceback):
        logger.error("Необработанное исключение", exc_info=(exctype, value, traceback))
        sys._excepthook(exctype, value, traceback)

    sys.excepthook = exception_hook

    # Таймер для дросселированного обновления UI
    update_timer = QtCore.QTimer()
    update_timer.timeout.connect(lambda: process_events_safely(app, logger))
    update_timer.start(50)  # 50 мс для плавного обновления

    # Таймер для мониторинга состояния приложения
    monitor_timer = QtCore.QTimer()
    monitor_timer.timeout.connect(lambda: monitor_app_state(main_window, logger, start_time))
    monitor_timer.start(5000)  # каждые 5 секунд

    main_window.show()
    sys.exit(app.exec_())


class GraphUpdateThread(QThread):
    update_signal = pyqtSignal()

    def __init__(self, main_window, logger):
        super().__init__()
        self.main_window = main_window
        self.logger = logger
        self.running = True

    def run(self):
        global last_graph_update
        while self.running:
            try:
                current_time = time.time()
                if hasattr(self.main_window, "market_graph") and self.main_window.market_graph is not None:
                    graph = self.main_window.market_graph
                    elapsed = current_time - last_graph_update

                    if elapsed > 0.05:  # 50 мс
                        self.update_signal.emit()
                        last_graph_update = current_time
                        self.logger.debug(f"[GRAPH_THREAD] График обновлен через {elapsed:.3f}с")
                time.sleep(0.016)  # ~60 FPS
            except Exception as e:
                self.logger.error(f"Ошибка в потоке обновления графика: {e}", exc_info=True)

    def stop(self):
        self.running = False


def optimize_graph_update(main_window, logger):
    """Оптимизирует обновление графика для устранения задержек"""
    global last_graph_update

    # Убираем избыточные обновления last_graph_update и централизуем его обновление
    def update_graph():
        try:
            if hasattr(main_window, "market_graph") and main_window.market_graph is not None:
                graph = main_window.market_graph
                if graph.full_price_data:
                    graph.update_graph(graph.full_price_data)
                    graph.repaint()
                    last_graph_update = time.time()  # Централизованное обновление времени
                else:
                    logger.warning("[GRAPH] Нет данных для обновления графика")
        except Exception as e:
            logger.error(f"Ошибка при обновлении графика: {e}", exc_info=True)

    # Создаем поток для обновления графика
    graph_thread = GraphUpdateThread(main_window, logger)
    graph_thread.update_signal.connect(update_graph)
    graph_thread.start()

    # Сохраняем поток в main_window, чтобы можно было остановить его при завершении
    main_window.graph_thread = graph_thread

    logger.info("[GRAPH] Поток обновления графика запущен")


def check_critical_state(main_window, logger):
    """Проверяет критические состояния и исправляет проблемы с отображением"""
    global graph_active, orders_shown

    try:
        current_time = time.time()

        # Проверяем, есть ли у нас окно с ордерами и отображается ли оно
        has_orders_window = False
        if hasattr(main_window, "order_window") and main_window.order_window is not None:
            has_orders_window = main_window.order_window.isVisible()

        # Если заметили изменение статуса окна с ордерами
        if has_orders_window != orders_shown:
            orders_shown = has_orders_window
            logger.warning(f"[CRITICAL] Статус окна с ордерами изменился на: {orders_shown}")

            # Если окно с ордерами появилось, обновляем график
            if orders_shown:
                force_graph_update(main_window, logger, current_time)

    except Exception as e:
        logger.error(f"Ошибка при проверке критического состояния: {e}", exc_info=True)


def force_graph_update(main_window, logger, start_time):
    """Принудительно обновляет график, независимо от других операций"""
    try:
        if hasattr(main_window, "market_graph") and main_window.market_graph is not None:
            graph = main_window.market_graph

            # Обновляем график
            graph.update()
            graph.repaint()

            elapsed = time.time() - start_time
            logger.debug(f"[GRAPH] Принудительное обновление графика за {elapsed:.3f}с")
    except Exception as e:
        logger.error(f"Ошибка при принудительном обновлении графика: {e}", exc_info=True)


def install_order_monitors(main_window, logger):
    """Устанавливает мониторы для отслеживания взаимодействия с ордерами"""
    try:
        # Проверяем наличие торгового симулятора
        if hasattr(main_window, "trading_simulator") and main_window.trading_simulator is not None:
            simulator = main_window.trading_simulator

            # Сохраняем оригинальные методы
            if hasattr(simulator, "create_order"):
                original_create_order = simulator.create_order

                # Переопределяем метод создания ордера
                def monitored_create_order(*args, **kwargs):
                    logger.info(f"[ORDER] Создание ордера: args={args}, kwargs={kwargs}")
                    result = original_create_order(*args, **kwargs)
                    logger.info(f"[ORDER] Ордер создан, результат: {result}")

                    # Установим таймер для обновления графика после создания ордера
                    QtCore.QTimer.singleShot(100, lambda: force_graph_update(main_window, logger, time.time()))

                    return result

                simulator.create_order = monitored_create_order
                logger.info("[MONITOR] Установлен монитор для create_order")

            # Монитор для execute_order если есть
            if hasattr(simulator, "execute_order"):
                original_execute_order = simulator.execute_order

                def monitored_execute_order(*args, **kwargs):
                    logger.info(f"[ORDER] Исполнение ордера: args={args}, kwargs={kwargs}")
                    result = original_execute_order(*args, **kwargs)
                    logger.info(f"[ORDER] Ордер исполнен, результат: {result}")

                    # Устанавливаем таймеры для обновления после исполнения ордера
                    QtCore.QTimer.singleShot(100, lambda: force_graph_update(main_window, logger, time.time()))

                    return result

                simulator.execute_order = monitored_execute_order
                logger.info("[MONITOR] Установлен монитор для execute_order")

    except Exception as e:
        logger.error(f"Ошибка при установке мониторов ордеров: {e}", exc_info=True)


def log_app_status(main_window, logger, start_time):
    """Логирует текущее состояние приложения"""
    try:
        elapsed = time.time() - start_time
        logger.info(f"[STATUS] Время работы: {elapsed:.2f}с")

        # Проверяем наличие ордеров
        if hasattr(main_window, "trading_simulator") and main_window.trading_simulator is not None:
            orders_count = getattr(main_window.trading_simulator, "orders_count", 0)
            logger.info(f"[ORDERS] Количество ордеров: {orders_count}")
    except Exception as e:
        logger.error(f"Ошибка при логировании статуса: {e}", exc_info=True)


def process_events_safely(app, logger):
    """Безопасная обработка событий с ограничением типов событий"""
    try:
        # Обрабатываем только UI события, исключая пользовательский ввод и сетевые уведомления
        app.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents | QtCore.QEventLoop.ExcludeSocketNotifiers)
    except Exception as e:
        logger.error(f"Ошибка при обработке событий: {e}", exc_info=True)


class EventLogger(QtCore.QObject):
    """Класс для низкоуровневого логирования событий Qt"""

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.event_counters = {}
        self.last_log_time = time.time()

        # Отслеживаем системные события, связанные с отрисовкой
        self.paint_events = set()
        self.critical_events = {"show": {}, "hide": {}, "paint": {}}

    def eventFilter(self, obj, event):
        # Логируем только важные события редко (чтобы не захламлять лог)
        event_type = event.type()

        # Считаем события по типам
        if event_type not in self.event_counters:
            self.event_counters[event_type] = 0
        self.event_counters[event_type] += 1

        # Расширенная проверка для объектов связанных с графиком и ордерами
        obj_name = obj.objectName() if hasattr(obj, "objectName") else str(obj)
        is_graph_related = any(
            keyword in obj_name.lower() for keyword in ["graph", "chart", "plot", "figure", "canvas"]
        )
        is_order_related = any(keyword in obj_name.lower() for keyword in ["order", "trade", "grid"])

        # Более подробное логирование для важных объектов
        if is_graph_related or is_order_related:
            if event_type == QtCore.QEvent.Show:
                self.logger.info(f"[EVENT] {obj_name} показан")
                self.critical_events["show"][obj_name] = time.time()
            elif event_type == QtCore.QEvent.Hide:
                self.logger.info(f"[EVENT] {obj_name} скрыт")
                self.critical_events["hide"][obj_name] = time.time()
            elif event_type == QtCore.QEvent.Paint:
                if obj_name not in self.paint_events:
                    self.paint_events.add(obj_name)
                    self.logger.info(f"[EVENT] {obj_name} отрисован")
                self.critical_events["paint"][obj_name] = time.time()

        # Периодически логируем статистику событий
        current_time = time.time()
        if current_time - self.last_log_time > 10:  # каждые 10 секунд
            self.logger.info(f"[EVENT_STATS] Статистика событий: {self.event_counters}")
            self.event_counters = {}

            # Сбрасываем отслеживание событий отрисовки для нового цикла
            self.paint_events = set()

            # Логируем критические события
            self.logger.info(f"[CRITICAL_EVENTS] Последние события show/hide/paint: {self.critical_events}")

            self.last_log_time = current_time

        return False  # Пропускаем событие дальше


class GraphMonitor(QtCore.QObject):
    """Класс для мониторинга состояния графика и аварийного восстановления"""

    def __init__(self, main_window, logger):
        super().__init__()
        self.main_window = main_window
        self.logger = logger
        self.last_update_time = time.time()
        self.stale_threshold = 5.0  # секунд без обновления
        self.recovery_attempts = 0
        self.max_recovery_attempts = 3

        # Запускаем таймер для проверки состояния
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.check_graph_state)
        self.timer.start(1000)  # проверка каждую секунду

    def check_graph_state(self):
        """Проверка состояния графика и восстановление при необходимости"""
        try:
            current_time = time.time()
            elapsed = current_time - self.last_update_time

            if elapsed > self.stale_threshold:
                self.logger.warning(f"[MONITOR] График не обновлялся {elapsed:.1f} секунд")

                if self.recovery_attempts < self.max_recovery_attempts:
                    self.recovery_attempts += 1
                    self.logger.info(f"[MONITOR] Попытка восстановления #{self.recovery_attempts}")

                    # Проверяем состояние графика и предпринимаем меры
                    if hasattr(self.main_window, "market_graph") and self.main_window.market_graph is not None:
                        graph = self.main_window.market_graph

                        # Форсированное обновление UI через прямой вызов
                        graph.update()
                        graph.repaint()

                        # Проверяем наличие данных
                        if hasattr(graph, "full_price_data") and graph.full_price_data:
                            # Сбрасываем кеш графика для перерисовки
                            graph.graphWidget.plotItem.getViewBox().autoRange()

                            # Восстанавливаем соединения сигналов
                            if hasattr(graph, "update_visible_range"):
                                graph.scroll_bar.valueChanged.disconnect()
                                graph.scroll_bar.valueChanged.connect(graph.update_visible_range)

                        # Принудительно обновляем торговый симулятор, если он доступен
                        if hasattr(self.main_window, "trading_simulator"):
                            simulator = self.main_window.trading_simulator
                            if simulator is not None:
                                # Быстрый перезапуск таймера симулятора
                                simulator.timer.stop()
                                simulator.timer.start(50)
                                # Принудительное обновление дисплея
                                QtCore.QTimer.singleShot(0, simulator.update_display)

                    self.last_update_time = current_time
                    self.logger.info("[MONITOR] Восстановление выполнено успешно")

                elif self.recovery_attempts == self.max_recovery_attempts:
                    # Крайние меры - перезапуск всей системы
                    self.logger.error("[MONITOR] Крайние меры - полное восстановление системы")

                    # Полная перезагрузка симулятора
                    if hasattr(self.main_window, "trading_simulator"):
                        simulator = self.main_window.trading_simulator
                        if simulator is not None:
                            simulator.stop()

                            # Пауза перед перезапуском для обработки событий
                            QtCore.QTimer.singleShot(500, simulator.start)

                    self.recovery_attempts += 1
                    self.last_update_time = current_time

                else:
                    self.logger.critical("[MONITOR] Превышено количество попыток восстановления")
            else:
                # Если обновление работает нормально
                self.recovery_attempts = 0
                self.last_update_time = current_time
        except Exception as e:
            self.logger.error(f"[MONITOR] Ошибка при проверке состояния: {str(e)}")


def update_ui_safely(main_window, logger):
    """Безопасное обновление UI с контролем ошибок"""
    try:
        if hasattr(main_window, "market_graph") and main_window.market_graph is not None:
            main_window.market_graph.update()
            main_window.market_graph.repaint()
            logger.debug("[UI] График обновлен")
    except Exception as e:
        logger.error(f"[UI] Ошибка при обновлении UI: {str(e)}")


def monitor_app_state(main_window, logger, start_time):
    """Мониторинг состояния приложения и производительности"""
    try:
        elapsed = time.time() - start_time
        memory_usage = get_memory_usage()
        cpu_usage = get_cpu_usage()

        logger.info(f"[STATUS] Время работы: {elapsed:.1f}с, RAM: {memory_usage:.1f}MB, CPU: {cpu_usage:.1f}%")

        # Проверяем состояние основных компонентов
        if hasattr(main_window, "trading_simulator"):
            simulator = main_window.trading_simulator
            if simulator is not None:
                order_count = len(simulator.order_manager.orders)
                price_history_len = len(simulator.prices)
                logger.info(f"[STATUS] Ордеров: {order_count}, Точек истории: {price_history_len}")
    except Exception as e:
        logger.error(f"[MONITOR] Ошибка при сборе статистики: {str(e)}")


def get_memory_usage():
    """Получение использования памяти процессом"""
    try:
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    except ImportError:
        # Если psutil не установлен
        return 0.0
    except Exception:
        return 0.0


def get_cpu_usage():
    """Получение использования CPU процессом"""
    try:
        import psutil

        process = psutil.Process()
        return process.cpu_percent()
    except ImportError:
        # Если psutil не установлен
        return 0.0
    except Exception:
        return 0.0


def profile_main():
    # Запуск с профилированием
    profiler = cProfile.Profile()
    profiler.enable()

    # Запускаем приложение на короткое время
    app = QtWidgets.QApplication([])
    main_window = MainWindow()
    main_window.show()

    # Устанавливаем автоматическое завершение после 30 секунд работы
    timer = QtCore.QTimer()
    timer.timeout.connect(app.quit)
    timer.start(30000)  # 30 секунд

    app.exec_()

    # Останавливаем профилирование и сохраняем результаты
    profiler.disable()

    # Сортируем по кумулятивному времени
    stats = pstats.Stats(profiler).sort_stats(SortKey.CUMULATIVE)
    stats.print_stats(30)  # Вывод 30 самых затратных функций

    # Сохраняем результаты в файл для детального анализа
    stats.dump_stats("profile_results.prof")
    print("Результаты профилирования сохранены в profile_results.prof")

    # Для удобства анализа можно использовать: python -m pstats profile_results.prof
    # Или визуализировать с помощью snakeviz: pip install snakeviz, затем snakeviz profile_results.prof


def install_start_simulation_monitor(main_window, logger, start_time):
    """Устанавливает обработчик для корректного запуска симуляции"""
    try:
        logger.info("[MONITOR] Установка обработчика запуска симуляции")

        # Если есть доступ к кнопке старта симуляции
        if hasattr(main_window, "start_button") and main_window.start_button is not None:
            # Отключаем существующий сигнал triggered для QAction
            if main_window.start_button.receivers(main_window.start_button.triggered) > 0:
                main_window.start_button.triggered.disconnect()

            # Создаем новый обработчик запуска
            def monitored_start_simulation():
                start_time_local = time.time()
                logger.info("[SIMULATION] Запуск симуляции")

                # Если есть симулятор, активируем его
                if hasattr(main_window, "simulator") and main_window.simulator is not None:
                    # Активируем обработку событий
                    main_window.events_enabled = True

                    # Активируем симулятор и его компоненты
                    main_window.simulator.order_manager.active = True
                    main_window.simulator.order_manager.processing_enabled = True

                    # Запускаем симуляцию
                    main_window.simulator.start()

                    logger.info(f"[SIMULATION] Симуляция запущена через {time.time() - start_time_local:.3f}с")
                else:
                    logger.error("[SIMULATION] Не удалось найти объект симулятора")

            main_window.start_button.triggered.connect(monitored_start_simulation)
            logger.info("[MONITOR] Обработчик запуска симуляции установлен")
        else:
            logger.warning("[MONITOR] Кнопка запуска не найдена, обработчик не установлен")

            # Пытаемся найти действия через меню
            for menu in main_window.menuBar().actions():
                for action in menu.menu().actions():
                    if action.text().lower() in ["start simulation", "старт симуляции", "запуск"]:
                        logger.info(f"[MONITOR] Найдено возможное действие запуска: {action.text()}")
                        action.triggered.connect(
                            lambda: logger.info("[SIMULATION] Запуск симуляции через найденное действие")
                        )

            # Также ищем кнопки
            for child in main_window.findChildren(QtWidgets.QPushButton):
                if child.text().lower() in ["start", "старт", "запуск"]:
                    logger.info(f"[MONITOR] Найдена возможная кнопка запуска: {child.text()}")
                    child.clicked.connect(lambda: logger.info("[SIMULATION] Запуск симуляции через найденную кнопку"))

    except Exception as e:
        logger.error(f"[MONITOR] Ошибка при установке обработчика запуска: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--profile":
        profile_main()
    else:
        main()

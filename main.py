import sys
import cProfile
import pstats
import logging
import time
import traceback
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
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("app_debug.log"),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger("grid_visualizer")
    detailed_handler = logging.FileHandler("detailed_debug.log")
    detailed_handler.setLevel(logging.DEBUG)
    detailed_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s - %(filename)s:%(lineno)d'
    ))
    logger.addHandler(detailed_handler)
    return logger


def main():
    logger = setup_logging()
    logger.info("Запуск приложения")
    start_time = time.time()
    
    app = QtWidgets.QApplication([])
    app.setStyle('Fusion')  # Используем Fusion стиль для лучшей производительности
    
    # Отключаем сглаживание для повышения производительности
    app.setAttribute(QtCore.Qt.AA_DisableHighDpiScaling, True)
    app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, False)
    
    # Устанавливаем обработчик исключений Qt
    sys._excepthook = sys.excepthook
    def exception_hook(exctype, value, traceback):
        logger.error("Необработанное исключение", exc_info=(exctype, value, traceback))
        sys._excepthook(exctype, value, traceback)
    sys.excepthook = exception_hook
    
    main_window = MainWindow()
    logger.info("Главное окно создано")
    
    # Устанавливаем переопределенный метод showEvent для MainWindow
    original_show_event = main_window.showEvent
    def enhanced_show_event(event):
        logger.info("[MAIN_WINDOW] Вызван showEvent")
        original_show_event(event)
    main_window.showEvent = enhanced_show_event
    
    # Таймер для общего обновления UI
    update_timer = QtCore.QTimer()
    update_timer.timeout.connect(lambda: process_events_safely(app, logger))
    update_timer.start(50)  # 50 мс для плавного обновления
    
    # Удаляем таймеры и вызовы force_graph_update, чтобы использовать только update_display
    # graph_update_timer.timeout.connect(lambda: force_graph_update(main_window, logger, start_time))
    # critical_refresh_timer.timeout.connect(lambda: check_critical_state(main_window, logger))
    
    # Еще один таймер для логирования состояния
    status_timer = QtCore.QTimer()
    status_timer.timeout.connect(lambda: log_app_status(main_window, logger, start_time))
    status_timer.start(5000)  # каждые 5 секунд
    
    logger.info("Отображение главного окна")
    main_window.show()

    # Устанавливаем обработчик для перехвата изменений в ордерах
    install_order_monitors(main_window, logger)
    
    # Устанавливаем низкоуровневые обработчики событий
    app.installEventFilter(EventLogger(logger))

    # Удаляем вызов optimize_graph_update, чтобы использовать только update_display из trading.py
    # optimize_graph_update(main_window, logger)

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
                if hasattr(self.main_window, 'market_graph') and self.main_window.market_graph is not None:
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
            if hasattr(main_window, 'market_graph') and main_window.market_graph is not None:
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
        if hasattr(main_window, 'order_window') and main_window.order_window is not None:
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
        if hasattr(main_window, 'market_graph') and main_window.market_graph is not None:
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
        if hasattr(main_window, 'trading_simulator') and main_window.trading_simulator is not None:
            simulator = main_window.trading_simulator
            
            # Сохраняем оригинальные методы
            if hasattr(simulator, 'create_order'):
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
            if hasattr(simulator, 'execute_order'):
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
        if hasattr(main_window, 'trading_simulator') and main_window.trading_simulator is not None:
            orders_count = getattr(main_window.trading_simulator, 'orders_count', 0)
            logger.info(f"[ORDERS] Количество ордеров: {orders_count}")
    except Exception as e:
        logger.error(f"Ошибка при логировании статуса: {e}", exc_info=True)


def process_events_safely(app, logger):
    try:
        app.processEvents()
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
        self.critical_events = {'show': {}, 'hide': {}, 'paint': {}}
    
    def eventFilter(self, obj, event):
        # Логируем только важные события редко (чтобы не захламлять лог)
        event_type = event.type()
        
        # Считаем события по типам
        if event_type not in self.event_counters:
            self.event_counters[event_type] = 0
        self.event_counters[event_type] += 1
        
        # Расширенная проверка для объектов связанных с графиком и ордерами
        obj_name = obj.objectName() if hasattr(obj, 'objectName') else str(obj)
        is_graph_related = any(keyword in obj_name.lower() for keyword in 
                              ['graph', 'chart', 'plot', 'figure', 'canvas'])
        is_order_related = any(keyword in obj_name.lower() for keyword in 
                              ['order', 'trade', 'grid'])
        
        # Более подробное логирование для важных объектов
        if is_graph_related or is_order_related:
            if event_type == QtCore.QEvent.Show:
                self.logger.info(f"[EVENT] {obj_name} показан")
                self.critical_events['show'][obj_name] = time.time()
            elif event_type == QtCore.QEvent.Hide:
                self.logger.info(f"[EVENT] {obj_name} скрыт")
                self.critical_events['hide'][obj_name] = time.time()
            elif event_type == QtCore.QEvent.Paint:
                if obj_name not in self.paint_events:
                    self.paint_events.add(obj_name)
                    self.logger.info(f"[EVENT] {obj_name} отрисован")
                self.critical_events['paint'][obj_name] = time.time()
                
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


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "--profile":
        profile_main()
    else:
        main()

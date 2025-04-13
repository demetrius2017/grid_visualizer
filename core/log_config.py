import logging
import os

# Настройка для специального логирования адаптивного шага сетки
def setup_adaptive_grid_logging():
    """
    Настраивает специальное логирование для адаптивного шага сетки.
    Создает отдельный файл adaptive_grid.log только для логов с тегами [TRADE_SPEED] и [GRID_STEP].
    """
    # Создаем директорию logs если не существует
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Путь к файлу логов
    log_file = os.path.join(log_dir, "adaptive_grid.log")
    
    # Создаем обработчик для файла
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    
    # Создаем форматтер с временной меткой
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    
    # Создаем фильтр для логов адаптивной сетки
    class AdaptiveGridFilter(logging.Filter):
        def filter(self, record):
            # Пропускаем только логи с тегами [TRADE_SPEED], [GRID_STEP] или [ADAPTIVE_GRID]
            return any(tag in record.getMessage() for tag in ["[TRADE_SPEED]", "[GRID_STEP]", "[ADAPTIVE_GRID]", "[TRADE_STATS]"])
    
    # Применяем фильтр
    file_handler.addFilter(AdaptiveGridFilter())
    
    # Получаем логгер для адаптивной сетки
    logger = logging.getLogger("adaptive_grid")
    logger.setLevel(logging.INFO)
    
    # Удаляем существующие обработчики
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Добавляем обработчик файла
    logger.addHandler(file_handler)
    
    # Создаем консольный обработчик для вывода в терминал
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(AdaptiveGridFilter())
    logger.addHandler(console_handler)
    
    # Отключаем передачу логов родительским логгерам
    logger.propagate = False
    
    return logger

# Пример использования:
# logger = setup_adaptive_grid_logging()
# logger.info("[ADAPTIVE_GRID] Логи адаптивной сетки настроены")
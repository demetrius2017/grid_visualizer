import time
import logging
from PyQt5 import QtCore, QtWidgets

class PerformanceMonitor:
    """Класс для мониторинга производительности обновления графика и UI"""
    
    def __init__(self, logger):
        self.logger = logger
        self.update_times = []
        self.max_samples = 100
        self.last_update = time.time()
        self.slow_updates = 0
        self.total_updates = 0
    
    def measure_start(self):
        """Начинает измерение времени операции"""
        return time.time()
    
    def measure_end(self, start_time, operation_name="Operation"):
        """Завершает измерение и логирует результат"""
        elapsed = time.time() - start_time
        self.total_updates += 1
        
        # Сохраняем время обновления для статистики
        self.update_times.append(elapsed)
        if len(self.update_times) > self.max_samples:
            self.update_times.pop(0)
        
        # Обновляем счетчик медленных обновлений
        if elapsed > 0.1:  # 100 мс считается медленным обновлением
            self.slow_updates += 1
            self.logger.warning(f"[PERFORMANCE] Медленное {operation_name}: {elapsed:.3f}с")
        
        # Считаем время с последнего обновления
        time_since_last = time.time() - self.last_update
        self.last_update = time.time()
        
        return elapsed, time_since_last
    
    def get_stats(self):
        """Возвращает текущую статистику производительности"""
        if not self.update_times:
            return {
                "avg_time": 0,
                "max_time": 0,
                "min_time": 0,
                "slow_ratio": 0,
                "updates_count": 0
            }
        
        return {
            "avg_time": sum(self.update_times) / len(self.update_times),
            "max_time": max(self.update_times),
            "min_time": min(self.update_times),
            "slow_ratio": self.slow_updates / max(1, self.total_updates),
            "updates_count": self.total_updates
        }
    
    def log_stats(self, prefix=""):
        """Логирует текущую статистику производительности"""
        stats = self.get_stats()
        self.logger.info(
            f"[PERFORMANCE] {prefix} Статистика обновлений: "
            f"среднее={stats['avg_time']:.3f}с, "
            f"макс={stats['max_time']:.3f}с, "
            f"мин={stats['min_time']:.3f}с, "
            f"медленных={stats['slow_ratio']*100:.1f}%, "
            f"всего={stats['updates_count']}"
        )
    
    def reset(self):
        """Сбрасывает статистику"""
        self.update_times = []
        self.slow_updates = 0
        self.total_updates = 0
        self.last_update = time.time()


def optimize_widget_for_performance(widget):
    """Оптимизирует виджет для лучшей производительности"""
    # Отключаем анимации
    widget.setProperty("animated", False)
    
    # Устанавливаем оптимальные флаги обновления
    widget.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
    widget.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
    
    # Для графических виджетов устанавливаем оптимальную политику обновления
    if hasattr(widget, 'setViewportUpdateMode'):
        widget.setViewportUpdateMode(QtWidgets.QGraphicsView.MinimalViewportUpdate)
    
    # Рекурсивно применяем оптимизацию к дочерним виджетам
    for child in widget.findChildren(QtWidgets.QWidget):
        optimize_widget_for_performance(child)

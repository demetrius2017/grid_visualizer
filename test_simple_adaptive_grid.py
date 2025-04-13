#!/usr/bin/env python
"""
Простой тестовый скрипт для проверки работы адаптивного шага сетки
"""

import os
import sys
import logging
import time
import random
from datetime import datetime

# Настраиваем пути импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем только наш модуль адаптивной сетки
from core.adaptive_grid import TradeSpeedCalculator, OrderType
from core.log_config import setup_adaptive_grid_logging

# Настраиваем логирование
logger = setup_adaptive_grid_logging()
logger.info("[TEST] Запуск теста адаптивного шага сетки")

# Создаем калькулятор с тестовыми параметрами
calculator = TradeSpeedCalculator(
    base_grid_step_percent=0.5,      # Базовый шаг сетки 0.5%
    maker_commission_rate=0.002,     # Комиссия мейкера 0.002 (0.2%)
    taker_commission_rate=0.005,     # Комиссия тейкера 0.005 (0.5%)
    max_grid_step_multiplier=2.0,    # Максимальное увеличение шага в 2 раза
    base_trade_speed=0.05,           # Базовая скорость сделок (1 сделка на 20 тиков)
    trade_speed_window=20            # Окно для расчета средней скорости
)

# Генерируем тестовые паттерны сделок с разной скоростью
def simulate_trades(num_trades=100, max_time=300):
    """
    Симулирует последовательность сделок с различной скоростью.
    
    Args:
        num_trades: количество сделок для симуляции
        max_time: максимальное время симуляции (в секундах)
    """
    logger.info("[TEST] Начало симуляции сделок")
    
    # Инициализация
    timestamp = 1000  # Начальная временная метка
    
    # Текущие шаги сетки для обоих типов ордеров
    buy_grid_step = calculator.base_grid_step
    sell_grid_step = calculator.base_grid_step
    
    # Паттерны скорости сделок
    patterns = [
        # Период низкой активности (редкие сделки)
        {"name": "Низкая активность", "min_interval": 30, "max_interval": 50, "duration": 10},
        
        # Период средней активности
        {"name": "Средняя активность", "min_interval": 15, "max_interval": 25, "duration": 20},
        
        # Период высокой активности (частые сделки)
        {"name": "Высокая активность", "min_interval": 5, "max_interval": 10, "duration": 15},
        
        # Период очень высокой активности (очень частые сделки)
        {"name": "Очень высокая активность", "min_interval": 1, "max_interval": 5, "duration": 10},
        
        # Возврат к средней активности
        {"name": "Возврат к средней", "min_interval": 15, "max_interval": 25, "duration": 15}
    ]
    
    # Симулируем сделки с разными паттернами скорости
    current_trades = 0
    start_time = time.time()
    
    for pattern in patterns:
        logger.info(f"[TEST] Период: {pattern['name']}, интервалы: {pattern['min_interval']}-{pattern['max_interval']} тиков")
        
        # Сколько сделок в этом паттерне
        pattern_trades = int(num_trades * (pattern['duration'] / sum(p['duration'] for p in patterns)))
        
        # Генерируем сделки для текущего паттерна
        for _ in range(pattern_trades):
            # Случайный интервал между сделками в этом паттерне
            interval = random.randint(pattern['min_interval'], pattern['max_interval'])
            timestamp += interval
            
            # Выбираем случайный тип ордера (buy/sell)
            order_type = OrderType.BUY.value if random.random() < 0.5 else OrderType.SELL.value
            
            # Обновляем скорость сделок
            calculator.update_trade_speed(order_type, timestamp)
            
            # Рассчитываем динамический шаг сетки
            new_grid_step = calculator.calculate_dynamic_grid_step(order_type)
            
            # Сохраняем текущий шаг для вывода изменений
            current_step = buy_grid_step if order_type == OrderType.BUY.value else sell_grid_step
            
            # Обновляем текущий шаг
            if order_type == OrderType.BUY.value:
                buy_grid_step = new_grid_step
            else:
                sell_grid_step = new_grid_step
            
            # Выводим статистику о сделке и шаге
            logger.info(f"[TEST] Сделка {current_trades+1}: {order_type}, интервал={interval}, шаг: {current_step:.4f}% -> {new_grid_step:.4f}%")
            
            # Выводим текущие скорости сделок
            if current_trades % 5 == 0:
                stats = calculator.get_trade_speed_stats()
                logger.info(f"[TEST] Текущие скорости - BUY: {stats['buy_speed']:.6f}, SELL: {stats['sell_speed']:.6f}")
            
            current_trades += 1
            
            # Проверяем условия выхода
            elapsed_time = time.time() - start_time
            if current_trades >= num_trades or elapsed_time >= max_time:
                break
        
        # Проверяем условия выхода из внешнего цикла
        if current_trades >= num_trades or time.time() - start_time >= max_time:
            break
    
    elapsed_time = time.time() - start_time
    logger.info(f"[TEST] Завершение симуляции: {current_trades} сделок за {elapsed_time:.2f} секунд")
    
    # Выводим финальную статистику
    stats = calculator.get_trade_speed_stats()
    logger.info(f"[TEST] Итоговые скорости - BUY: {stats['buy_speed']:.6f}, SELL: {stats['sell_speed']:.6f}")
    logger.info(f"[TEST] Итоговые шаги сетки - BUY: {buy_grid_step:.4f}%, SELL: {sell_grid_step:.4f}%")
    logger.info(f"[TEST] Мин. безопасный шаг сетки: {calculator.min_grid_step:.4f}%")

# Запуск симуляции
if __name__ == "__main__":
    # Количество сделок для симуляции
    num_trades = 100
    
    # Максимальное время симуляции в секундах
    max_time = 60
    
    try:
        # Запускаем симуляцию
        simulate_trades(num_trades, max_time)
        
        # Выводим пути к файлам логов
        log_file = os.path.abspath("logs/adaptive_grid.log")
        print(f"\nТестирование завершено!")
        print(f"Логи адаптивного шага сетки: {log_file}")
        
    except Exception as e:
        logger.error(f"[TEST] Ошибка при выполнении теста: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
#!/usr/bin/env python
"""
Скрипт для тестирования адаптивного шага сетки с расширенным временем и фокусом только на нужных логах
"""

import os
import sys
import logging
import argparse

# Добавляем корневую директорию проекта в путь импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.log_config import setup_adaptive_grid_logging
from main import run_headless_simulation


def run_adaptive_grid_test(
    csv_file="data/solana_minute_compact_final.csv",
    max_positions=100,  # Увеличиваем количество позиций до 100
    timeout=600,  # Увеличиваем время тестирования до 10 минут
    output_path="logs/adaptive_grid_simulation.txt",
):
    """
    Запускает тестирование адаптивного шага сетки с фокусом только на логах адаптивной сетки
    """
    # Настраиваем логирование адаптивной сетки
    logger = setup_adaptive_grid_logging()
    logger.info("[ADAPTIVE_GRID] Запуск тестирования адаптивного шага сетки")
    
    # Отключаем стандартное логирование
    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.setLevel(logging.ERROR)  # Оставляем только ошибки в основном логгере
    
    # Запускаем симуляцию с расширенными параметрами
    run_headless_simulation(
        csv_file=csv_file,
        max_positions=max_positions,
        stop_after_positions=True,
        timeout=timeout,
        output_path=output_path,
    )
    
    # Восстанавливаем уровень логирования
    root_logger.setLevel(original_level)
    
    logger.info("[ADAPTIVE_GRID] Тестирование адаптивного шага сетки завершено")
    
    # Выводим путь к логам для удобства
    print(f"\nТестирование завершено!")
    print(f"Логи адаптивной сетки: {os.path.abspath('logs/adaptive_grid.log')}")
    print(f"Результаты симуляции: {os.path.abspath(output_path)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Тестирование адаптивного шага сетки")
    parser.add_argument("--csv", type=str, default="data/solana_minute_compact_final.csv",
                        help="Путь к CSV файлу с данными")
    parser.add_argument("--max-positions", type=int, default=100,
                        help="Максимальное количество позиций для обработки")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Тайм-аут в секундах (по умолчанию 600 - 10 минут)")
    parser.add_argument("--output", type=str, default="logs/adaptive_grid_simulation.txt",
                        help="Путь для сохранения отчета о симуляции")
    
    args = parser.parse_args()
    
    # Запускаем тестирование с параметрами из командной строки
    run_adaptive_grid_test(
        csv_file=args.csv,
        max_positions=args.max_positions,
        timeout=args.timeout,
        output_path=args.output,
    )
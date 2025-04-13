"""
Модуль для реализации адаптивного шага сетки на основе скорости сделок

Этот модуль предоставляет функциональность для:
1. Отслеживания скорости сделок в относительном тиковом времени
2. Адаптивного изменения шага сетки на основе скорости сделок
3. Поддержания минимального шага сетки на уровне (комиссия тейкера + комиссия мейкера) * 2
"""

import logging
import time
from enum import Enum


class OrderType(Enum):
    BUY = "buy"
    SELL = "sell"


class TradeSpeedCalculator:
    """
    Класс для расчета скорости сделок и адаптивного шага сетки
    """

    def __init__(
        self,
        base_grid_step_percent,
        maker_commission_rate,
        taker_commission_rate,
        max_grid_step_multiplier=2.0,
        base_trade_speed=0.05,
        trade_speed_window=20
    ):
        """
        Инициализация калькулятора скорости сделок
        
        Args:
            base_grid_step_percent (float): Базовый шаг сетки в процентах
            maker_commission_rate (float): Комиссия мейкера в процентах
            taker_commission_rate (float): Комиссия тейкера в процентах
            max_grid_step_multiplier (float): Максимальный множитель шага сетки
            base_trade_speed (float): Базовая скорость сделок для нормализации
            trade_speed_window (int): Размер окна для расчета средней скорости сделок
        """
        # Создаем собственный логгер для адаптивного шага
        self.logger = logging.getLogger("adaptive_grid")
        # Настраиваем уровень логирования
        self.logger.setLevel(logging.INFO)
        
        # Базовые параметры
        self.base_grid_step = base_grid_step_percent
        self.max_grid_step_multiplier = max_grid_step_multiplier
        self.base_trade_speed = base_trade_speed
        self.trade_speed_window = trade_speed_window
        
        # Минимальный шаг на основе комиссий
        self.min_grid_step = (maker_commission_rate + taker_commission_rate) * 2 * 100  # в процентах
        
        # Счетчики последовательных сделок
        self.consecutive_buys = 0
        self.consecutive_sells = 0
        
        # История сделок и метки времени
        self.buy_trades_history = []  # История сделок на покупку [тик, время между сделками]
        self.sell_trades_history = []  # История сделок на продажу [тик, время между сделками]
        
        # Временные метки последних сделок
        self.last_buy_trade_tick = 0
        self.last_sell_trade_tick = 0
        
        # Текущие скорости сделок
        self.buy_trade_speed = 0.0  # Скорость сделок на покупку (сделок/тик)
        self.sell_trade_speed = 0.0  # Скорость сделок на продажу (сделок/тик)

        self.logger.info(f"[ADAPTIVE_GRID] Инициализирован с параметрами: шаг={base_grid_step_percent}%, мин_шаг={self.min_grid_step}%, макс_множитель={max_grid_step_multiplier}")

    def update_trade_speed(self, order_type, timestamp):
        """
        Обновляет скорость сделок для заданного типа ордеров.
        Скорость измеряется в относительном тиковом времени (сделок/тик).
        
        Args:
            order_type (str): тип ордера ("buy" или "sell")
            timestamp (int): текущая временная метка (тик)
            
        Returns:
            float: Текущая скорость сделок (сделок/тик)
        """
        if order_type == OrderType.BUY.value:
            # Обновляем счетчики последовательных сделок
            self.consecutive_buys += 1
            self.consecutive_sells = 0
            
            # Рассчитываем время (в тиках) с последней сделки на покупку
            if self.last_buy_trade_tick > 0:
                ticks_since_last_trade = timestamp - self.last_buy_trade_tick
                
                # Добавляем информацию о сделке в историю
                self.buy_trades_history.append([timestamp, ticks_since_last_trade])
                
                # Всегда логируем информацию о новой сделке
                self.logger.info(f"[TRADE_SPEED] Новая BUY сделка, тики с предыдущей: {ticks_since_last_trade}")
                
                # Ограничиваем размер истории
                if len(self.buy_trades_history) > self.trade_speed_window:
                    self.buy_trades_history.pop(0)
                
                # Рассчитываем среднюю скорость сделок (1/среднее время между сделками)
                if len(self.buy_trades_history) > 0:
                    avg_ticks_between_trades = sum(trade[1] for trade in self.buy_trades_history) / len(self.buy_trades_history)
                    if avg_ticks_between_trades > 0:
                        new_speed = 1.0 / avg_ticks_between_trades
                        
                        # Всегда логируем изменение скорости
                        speed_change = abs(new_speed - self.buy_trade_speed) / max(self.buy_trade_speed, 0.0001)
                        self.logger.info(f"[TRADE_SPEED] BUY скорость: {self.buy_trade_speed:.6f} -> {new_speed:.6f} (изменение: {speed_change:.2%}, среднее время: {avg_ticks_between_trades:.1f} тиков)")
                        
                        self.buy_trade_speed = new_speed
            
            # Обновляем временную метку последней сделки
            self.last_buy_trade_tick = timestamp
            
            return self.buy_trade_speed
            
        elif order_type == OrderType.SELL.value:
            # Обновляем счетчики последовательных сделок
            self.consecutive_sells += 1
            self.consecutive_buys = 0
            
            # Рассчитываем время (в тиках) с последней сделки на продажу
            if self.last_sell_trade_tick > 0:
                ticks_since_last_trade = timestamp - self.last_sell_trade_tick
                
                # Добавляем информацию о сделке в историю
                self.sell_trades_history.append([timestamp, ticks_since_last_trade])
                
                # Всегда логируем информацию о новой сделке
                self.logger.info(f"[TRADE_SPEED] Новая SELL сделка, тики с предыдущей: {ticks_since_last_trade}")
                
                # Ограничиваем размер истории
                if len(self.sell_trades_history) > self.trade_speed_window:
                    self.sell_trades_history.pop(0)
                
                # Рассчитываем среднюю скорость сделок (1/среднее время между сделками)
                if len(self.sell_trades_history) > 0:
                    avg_ticks_between_trades = sum(trade[1] for trade in self.sell_trades_history) / len(self.sell_trades_history)
                    if avg_ticks_between_trades > 0:
                        new_speed = 1.0 / avg_ticks_between_trades
                        
                        # Всегда логируем изменение скорости
                        speed_change = abs(new_speed - self.sell_trade_speed) / max(self.sell_trade_speed, 0.0001)
                        self.logger.info(f"[TRADE_SPEED] SELL скорость: {self.sell_trade_speed:.6f} -> {new_speed:.6f} (изменение: {speed_change:.2%}, среднее время: {avg_ticks_between_trades:.1f} тиков)")
                        
                        self.sell_trade_speed = new_speed
            
            # Обновляем временную метку последней сделки
            self.last_sell_trade_tick = timestamp
            
            return self.sell_trade_speed
        
        # Логируем текущие скорости для обоих типов
        if self.last_buy_trade_tick > 0 and self.last_sell_trade_tick > 0:
            self.logger.info(f"[TRADE_SPEED] Текущие скорости: BUY={self.buy_trade_speed:.6f}, SELL={self.sell_trade_speed:.6f}")
        
        return 0.0  # Если передан неизвестный тип ордера

    def calculate_dynamic_grid_step(self, order_type):
        """
        Рассчитывает динамический шаг сетки на основе скорости сделок.
        Шаг адаптивно увеличивается при росте скорости сделок и уменьшается при падении.
        Никогда не опускается ниже минимального безопасного значения.
        
        Args:
            order_type (str): тип ордера ("buy" или "sell")
            
        Returns:
            float: шаг сетки в процентах
        """
        # Определяем текущую скорость сделок для заданного типа ордера
        trade_speed = self.buy_trade_speed if order_type == OrderType.BUY.value else self.sell_trade_speed
        
        # Если скорость сделок ещё не измерена (нет истории), используем счетчики последовательных сделок
        if trade_speed <= 0.000001:
            if order_type == OrderType.BUY.value:
                multiplier = min(2 ** self.consecutive_buys, self.max_grid_step_multiplier)
                self.logger.info(f"[GRID_STEP] BUY шаг на основе последовательности ({self.consecutive_buys}): x{multiplier:.2f}")
            else:  # sell
                multiplier = min(2 ** self.consecutive_sells, self.max_grid_step_multiplier)
                self.logger.info(f"[GRID_STEP] SELL шаг на основе последовательности ({self.consecutive_sells}): x{multiplier:.2f}")
            
            # Рассчитываем новый шаг и гарантируем, что он не ниже минимального
            calculated_step = self.base_grid_step * multiplier
            grid_step = max(calculated_step, self.min_grid_step)
            
            # Логируем подробную информацию о расчете
            if grid_step == self.min_grid_step and calculated_step < self.min_grid_step:
                self.logger.info(f"[GRID_STEP] {order_type} шаг ограничен минимальным: {grid_step:.4f}% (рассчитано: {calculated_step:.4f}%)")
            else:
                self.logger.info(f"[GRID_STEP] {order_type} шаг: {grid_step:.4f}% (базовый: {self.base_grid_step:.4f}%)")
            
            return grid_step
        
        # Вычисляем коэффициент изменения шага на основе отношения текущей скорости к базовой
        speed_ratio = trade_speed / self.base_trade_speed
        
        # Логирование для отладки
        self.logger.info(f"[GRID_STEP] {order_type} trade_speed={trade_speed:.6f}, base_speed={self.base_trade_speed:.6f}, ratio={speed_ratio:.2f}")
        
        # Если скорость выше базовой, увеличиваем шаг пропорционально
        if speed_ratio > 1.0:
            # Ограничиваем максимальный множитель
            multiplier = min(speed_ratio, self.max_grid_step_multiplier)
            self.logger.info(f"[GRID_STEP] {order_type} УВЕЛИЧЕНИЕ шага из-за высокой скорости: x{multiplier:.2f}")
        # Если скорость ниже базовой, уменьшаем шаг пропорционально, но не ниже минимального
        else:
            # Множитель минимум 0.5 (уменьшение шага не более чем в 2 раза)
            multiplier = max(speed_ratio, 0.5)
            self.logger.info(f"[GRID_STEP] {order_type} УМЕНЬШЕНИЕ шага из-за низкой скорости: x{multiplier:.2f}")
        
        # Рассчитываем новый шаг на основе множителя
        calculated_step = self.base_grid_step * multiplier
        
        # Проверяем, не ниже ли он минимального порога
        grid_step = max(calculated_step, self.min_grid_step)
        
        # Подробное логирование, показывающее ограничение минимальным шагом
        if grid_step == self.min_grid_step and calculated_step < self.min_grid_step:
            self.logger.info(f"[GRID_STEP] {order_type} шаг ограничен минимальным: {grid_step:.4f}% (рассчитано: {calculated_step:.4f}%)")
        else:
            self.logger.info(f"[GRID_STEP] {order_type} ИТОГОВЫЙ шаг: {grid_step:.4f}% (рассчитано: {calculated_step:.4f}%)")
        
        return grid_step

    def get_trade_speed_stats(self):
        """
        Возвращает статистику по скорости сделок.
        
        Returns:
            dict: словарь со статистикой скорости сделок
        """
        # Средние интервалы между сделками
        avg_buy_interval = 0
        if self.buy_trades_history:
            avg_buy_interval = sum(trade[1] for trade in self.buy_trades_history) / len(self.buy_trades_history)
            
        avg_sell_interval = 0 
        if self.sell_trades_history:
            avg_sell_interval = sum(trade[1] for trade in self.sell_trades_history) / len(self.sell_trades_history)
        
        # Логируем текущую статистику
        self.logger.info(f"[TRADE_STATS] BUY: скорость={self.buy_trade_speed:.6f}, интервал={avg_buy_interval:.1f}, история={len(self.buy_trades_history)}")
        self.logger.info(f"[TRADE_STATS] SELL: скорость={self.sell_trade_speed:.6f}, интервал={avg_sell_interval:.1f}, история={len(self.sell_trades_history)}")
        
        # Возвращаем статистику
        return {
            "buy_speed": self.buy_trade_speed,
            "sell_speed": self.sell_trade_speed,
            "buy_consecutive": self.consecutive_buys,
            "sell_consecutive": self.consecutive_sells,
            "buy_avg_interval": avg_buy_interval,
            "sell_avg_interval": avg_sell_interval,
            "buy_history_size": len(self.buy_trades_history),
            "sell_history_size": len(self.sell_trades_history),
            "last_buy_tick": self.last_buy_trade_tick,
            "last_sell_tick": self.last_sell_trade_tick
        }


# Пример использования:
"""
# Создаем калькулятор с базовыми параметрами
calculator = TradeSpeedCalculator(
    base_grid_step_percent=0.5,      # Базовый шаг сетки 0.5%
    maker_commission_rate=0.0002,    # Комиссия мейкера 0.0002 (0.02%)
    taker_commission_rate=0.0005,    # Комиссия тейкера 0.0005 (0.05%)
    max_grid_step_multiplier=2.0,    # Максимальное увеличение шага в 2 раза
    base_trade_speed=0.05,           # Базовая скорость сделок
    trade_speed_window=20            # Окно для расчета средней скорости
)

# Обновляем скорость сделок при исполнении ордера
timestamp = 1000  # Временная метка текущего тика
calculator.update_trade_speed("buy", timestamp)

# Рассчитываем динамический шаг сетки
buy_step = calculator.calculate_dynamic_grid_step("buy")
sell_step = calculator.calculate_dynamic_grid_step("sell")

print(f"Динамический шаг для buy ордеров: {buy_step}%")
print(f"Динамический шаг для sell ордеров: {sell_step}%")
"""
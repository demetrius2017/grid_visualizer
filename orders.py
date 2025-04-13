import uuid
import numpy as np
from scipy import stats
import logging
from options_manager import OptionsManager
from core.adaptive_grid import TradeSpeedCalculator  # Импорт класса для адаптивного шага сетки


# Константы для комиссий Binance
MAKER_COMMISSION_RATE = 0.002  # 0.02%
TAKER_COMMISSION_RATE = 0.005  # 0.05%
MIN_VOLUME_THRESHOLD = 0.1


class Position:
    def __init__(self, order_type, price, volume, is_maker=True):
        self.order_type = order_type  # buy or sell
        self.entry_price = price
        self.volume = volume
        self.floating_profit = 0
        self.closed = False
        self.exit_price = None
        self.profit = 0
        self.margin = price * volume  # Используемая маржа
        self.commission = price * volume * (MAKER_COMMISSION_RATE if is_maker else TAKER_COMMISSION_RATE)

    def update_floating_profit(self, current_price):
        """Обновляет плавающую прибыль позиции"""
        if not self.closed:
            if self.order_type == "buy":
                self.floating_profit = (current_price - self.entry_price) * self.volume
            else:  # sell
                self.floating_profit = (self.entry_price - current_price) * self.volume
            return self.floating_profit
        return 0

    def close_position(self, exit_price, is_maker=True):
        """Закрывает позицию с расчетом финальной прибыли и высвобождением маржи"""
        if not self.closed:
            self.exit_price = exit_price
            self.closed = True

            # Комиссия за закрытие позиции
            exit_commission = exit_price * self.volume * (MAKER_COMMISSION_RATE if is_maker else TAKER_COMMISSION_RATE)
            total_commission = self.commission + exit_commission

            # Расчет прибыли с учетом комиссий
            if self.order_type == "buy":
                self.profit = (exit_price - self.entry_price) * self.volume - total_commission
            else:  # sell
                self.profit = (self.entry_price - exit_price) * self.volume - total_commission

            # Обнуляем плавающую прибыль при закрытии
            self.floating_profit = 0

            # Сохраняем освобождаемую маржу для возврата
            released_margin = self.margin
            # Полностью обнуляем маржу при закрытии
            self.margin = 0

            logger = logging.getLogger("grid_visualizer")
            logger.info(
                f"[POSITION] Position closed: {self.order_type}, volume={self.volume:.8f}, profit={self.profit:.8f}, released margin={released_margin:.8f}"
            )
            logger.info(
                f"[POSITION] Entry price: {self.entry_price:.8f}, Exit price: {exit_price:.8f}, Volume: {self.volume:.8f}"
            )
            logger.info(
                f"[POSITION] Commission: {total_commission:.8f} (Entry: {self.commission:.8f}, Exit: {exit_commission:.8f})"
            )

            # Возвращаем освобожденную маржу для обработки в вызывающем коде
            return self.profit, released_margin
        else:
            logger = logging.getLogger("grid_visualizer")
            logger.warning(
                f"[POSITION] Attempt to close already closed position: type={self.order_type}, entry={self.entry_price:.8f}, vol={self.volume:.8f}"
            )
            return 0, 0


class Order:
    def __init__(self, order_type, price, volume, is_maker=True):
        self.id = str(uuid.uuid4())[:8]
        self.order_type = order_type
        self.price = price
        self.volume = volume
        self.executed = False
        self.execution_price = None
        self.execution_time = None
        self.profit = 0
        self.is_maker = is_maker
        self.commission = price * volume * (MAKER_COMMISSION_RATE if is_maker else TAKER_COMMISSION_RATE)


class OrderManager:
    def __init__(
        self,
        initial_balance,
        grid_size,
        graph,
        grid_step_percent,
        min_grid_coverage,
        min_orders,
        max_orders,
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.grid_size = grid_size
        self.grid_step_percent = grid_step_percent
        self.min_grid_coverage = min_grid_coverage
        self.min_orders = min_orders
        self.max_orders = max_orders
        self.orders = []
        self.executed_orders = []
        self.order_history = []
        self.profit = 0
        self.floating_profit = 0
        self.free_margin = initial_balance
        self.current_ema = None  # Хранение текущего значения EMA
        self.current_price = None  # Хранение текущей цены
        self.graph = graph
        self.positions = []
        self.closed_positions = []
        self.executed_orders_history = []
        self.price_distribution = []
        self.distribution_period = 1000  # Количество последних цен для анализа
        self.num_bins = 50  # Количество столбиков в гистограмме
        self.price_frequency = {}
        # Новые атрибуты для динамического шага сетки
        self.consecutive_buys = 0
        self.consecutive_sells = 0
        self.total_profit = 0
        self.total_commission = 0
        # Атрибуты для отслеживания скорости сделок
        self.buy_trades_history = []  # История сделок на покупку [тик, цена]
        self.sell_trades_history = []  # История сделок на продажу [тик, цена]
        self.trade_speed_window = 20  # Окно для расчета скорости (количество последних сделок)
        self.last_buy_trade_tick = 0  # Последний тик сделки на покупку
        self.last_sell_trade_tick = 0  # Последний тик сделки на продажу
        self.buy_trade_speed = 0.0  # Скорость сделок на покупку (сделок/тик)
        self.sell_trade_speed = 0.0  # Скорость сделок на продажу (сделок/тик)
        self.base_trade_speed = 0.05  # Базовая скорость сделок (для нормализации)
        self.min_grid_step = (MAKER_COMMISSION_RATE + TAKER_COMMISSION_RATE) * 2 * 100  # Минимальный шаг в процентах
        # Существующая инициализация...
        self.options_manager = OptionsManager()
        self.hedge_active = False
        self.hedge_update_frequency = 24 * 60  # Обновление хеджа раз в сутки
        self.hedge_counter = 0

        # Добавляем параметры для периодической проверки
        self.grid_check_interval = 50  # Проверять каждые 50 тиков
        self.grid_check_counter = 0
        self.last_ema = None
        self.ema_threshold = 0.001  # Порог изменения EMA в процентах
        # Добавляем атрибут для границ сетки
        self.current_grid_bounds = None
        # Устанавливаем более агрессивные параметры для сетки
        self.volume_growth_factor = 1.05  # Уменьшаем рост объема для более равномерного распределения средств
        self.base_grid_step = grid_step_percent
        self.max_grid_step_multiplier = 2  # Уменьшаем множитель для более плотной сетки
        self.initial_grid_created = False  # Флаг для отслеживания создания начальной сетки
        self.price_history = [0.5]  # Инициализируем историю цен
        # Добавляем базовый фиксированный объем
        self.base_fixed_volume = 1.0
        self.low_margin_triggered = False
        self.virtual_grid = {"buy": [], "sell": []}

        # Флаг разрешения создания ордеров - ВАЖНО: установлен в False!
        self.orders_enabled = False

        # Временные метки
        self.timestamps = []

        # Явно отключаем любые фоновые операции до запуска
        self.processing_enabled = False

        # Новый флаг, чтобы отключить все операции до явного разрешения
        self.active = False

    def check_grid_state(self):
        """Проверка состояния сетки and необходимости её обновления"""
        if self.options_manager.last_trigger_price:
            return False

        # Проверяем по таймеру
        if self.grid_check_counter >= self.grid_check_interval:
            self.grid_check_counter = 0  # Сбрасываем счетчик

            # Проверяем изменение EMA
            if self.last_ema is not None and self.current_ema is not None:
                ema_change = abs(self.current_ema - self.last_ema) / self.last_ema
                if ema_change > self.ema_threshold:
                    print(f"Significant EMA change detected: {ema_change:.4%}")
                    self.last_ema = self.current_ema
                    return True

            # Проверяем наличие ордеров в обоих направлениях
            active_orders = [order for order in self.orders if not order.executed]
            active_buy_orders = [order for order in active_orders if order.order_type == "buy"]
            active_sell_orders = [order for order in active_orders if order.order_type == "sell"]

            if len(active_orders) == 0:
                print("No active orders, updating grid")
                return True
            elif len(active_buy_orders) == 0:
                print("No buy orders, updating grid")
                return True
            elif len(active_sell_orders) == 0:
                print("No sell orders, updating grid")
                return True

            # Проверяем расположение ордеров относительно текущей цены
            if active_buy_orders:
                closest_buy = max(order.price for order in active_buy_orders)
                if (self.current_price - closest_buy) / self.current_price > self.grid_step_percent / 100:
                    print("Buy orders too far from current price")
                    return True

            if active_sell_orders:
                closest_sell = min(order.price for order in active_sell_orders)
                if (closest_sell - self.current_price) / self.current_price > self.grid_step_percent / 100:
                    print("Sell orders too far from current price")
                    return True

        return False

    def update_grid(self, ema, current_price, price_history):
        """Простое обновление сетки ордеров: удаляем старые, создаем ровно min_orders вверх and вниз"""
        print(f"Updating grid at price {current_price}, EMA: {ema}")

        # Сохраняем текущее значение EMA
        self.last_ema = ema

        # Удаляем все ордера
        self.orders = [order for order in self.orders if order.executed]

        # Задаем новую сетку вокруг текущей цены
        base_volume = self.calculate_base_volume(current_price)

        # Buy ордера вниз от текущей цены
        buy_prices = []
        for i in range(self.min_orders):
            price = ema * (1 - self.grid_step_percent / 100 * (i + 1))
            buy_prices.append(price)

        # Sell ордера вверх от текущей цены
        sell_prices = []
        for i in range(self.min_orders):
            price = ema * (1 + self.grid_step_percent / 100 * (i + 1))
            sell_prices.append(price)

        for i, price in enumerate((buy_prices)):  # Сначала дальние, потом ближние
            volume = base_volume * (self.volume_growth_factor**i)
            if price < ema and price < current_price:
                self.place_order("buy", price, volume)

        for i, price in enumerate((sell_prices)):
            volume = base_volume * (self.volume_growth_factor**i)
            if price > ema and price > current_price:
                self.place_order("sell", price, volume)

        self.current_grid_bounds = (min(buy_prices), max(sell_prices))

    def update_price_distribution(self, price):
        self.price_distribution.append(price)
        if len(self.price_distribution) > self.distribution_period:
            self.price_distribution.pop(0)

        # Обновляем частоту цен
        price_bin = round(price, 4)  # Округляем до двух знаков после запятой
        self.price_frequency[price_bin] = self.price_frequency.get(price_bin, 0) + 1

    def get_price_distribution_data(self):
        if len(self.price_distribution) < 2:
            return None

        mean = np.mean(self.price_distribution)
        std = np.std(self.price_distribution)
        hist, bin_edges = np.histogram(self.price_distribution, bins=self.num_bins, density=True)

        # Вычисляем нормальное распределение для сравнения
        x = np.linspace(min(self.price_distribution), max(self.price_distribution), 100)
        normal_dist = stats.norm.pdf(x, mean, std)

        # Находим максимальное значение плотности вероятности
        max_density = max(max(hist), max(normal_dist))

        # Нормализуем гистограмму and нормальное распределение
        hist_normalized = hist / max_density
        normal_dist_normalized = normal_dist / max_density

        return {
            "hist": hist_normalized.tolist(),
            "bin_edges": bin_edges.tolist(),
            "normal_dist": normal_dist_normalized.tolist(),
            "x": x.tolist(),
            "current_price": self.current_price,
        }

    def calculate_distribution_coefficient(self):
        if len(self.executed_orders_history) < self.distribution_period:
            return 1.0  # Возвращаем нейтральный коэффициент, если недостаточно данных

        recent_orders = self.executed_orders_history[-self.distribution_period :]
        buy_count = sum(1 for order in recent_orders if order.order_type == "buy")
        sell_count = len(recent_orders) - buy_count
        if sell_count == 0:
            return 2.0  # Максимальный коэффициент в пользу покупок
        return buy_count / sell_count

    def calculate_price_frequency_coefficient(self, price):
        if not self.price_frequency:
            return 1.0

        price_bin = round(price, 2)
        frequency = self.price_frequency.get(price_bin, 0)
        max_frequency = max(self.price_frequency.values())

        if max_frequency == 0:
            return 1.0

        # Инвертируем коэффициент, чтобы редкие цены получали больший объем
        return 1 + (1 - frequency / max_frequency)

    def calculate_grid_boundaries(self, ema, price_history):
        hist_min = np.min(price_history)
        hist_max = np.max(price_history)
        current_price = price_history[-1]

        # Рассчитываем минимальный шаг сетки
        min_step = current_price * (self.grid_step_percent / 100)

        # Рассчитываем расстояние от текущей цены до исторического максимума and минимума
        distance_to_max = (hist_max - current_price) / current_price
        distance_to_min = (current_price - hist_min) / current_price

        # # Устанавливаем верхнюю and нижнюю границы сетки
        # upper_bound = ema * (1 + max(distance_to_min, self.min_grid_coverage))
        # lower_bound = ema * (1 - max(distance_to_max, self.min_grid_coverage))
        # Устанавливаем верхнюю and нижнюю границы сетки
        upper_bound = current_price + min_step * self.max_orders
        lower_bound = current_price - min_step * self.max_orders

        # Убедимся, что границы не выходят за исторический диапазон
        upper_bound = min(upper_bound, hist_max)
        lower_bound = max(lower_bound, hist_min)

        # Убедимся, что границы достаточно далеки от текущей цены
        upper_bound = max(upper_bound, current_price + min_step * self.min_orders)
        lower_bound = min(lower_bound, current_price - min_step * self.min_orders)

        # print(f"Grid boundaries: Lower = {lower_bound}, Upper = {upper_bound}")
        return lower_bound, upper_bound

    def place_order(self, order_type, price, volume):
        """Размещение ордера с проверкой маржи"""

        # Проверяем, включено ли создание ордеров
        if not self.orders_enabled:
            return False

        # Проверяем количество активных ордеров
        active_orders_count = len([order for order in self.orders if not order.executed])
        if active_orders_count >= self.max_orders * 2:  # Максимальное количество ордеров (buy + sell)
            print(f"ERROR: Maximum orders limit reached ({active_orders_count}/{self.max_orders * 2})")
            return False

        required_margin = price * volume
        estimated_commission = price * volume * MAKER_COMMISSION_RATE
        total_required = required_margin + estimated_commission

        logger = logging.getLogger("grid_visualizer")
        logger.info(
            f"[MARGIN_DEBUG] Перед размещением ордера {order_type}: свободная маржа={self.free_margin:.8f}, требуется={total_required:.8f}"
        )

        # Проверяем, есть ли свободная маржа
        if self.free_margin <= 0:
            print(f"ERROR: Free margin is negative ({self.free_margin:.8f}). Cannot place order.")
            return False

        # Добавляем проверку минимального объема
        min_volume = 0.001  # Минимальный допустимый объем
        if volume < min_volume:
            print(f"ERROR: Volume {volume:.8f} is below minimum {min_volume}")
            return False

        # Проверяем, не превышает ли требуемая маржа определенный процент от свободной маржи
        max_margin_per_order = self.free_margin * 0.2  # Максимум 20% свободной маржи на один ордер
        if total_required > max_margin_per_order:
            print(f"ERROR: Required margin {total_required:.8f} exceeds max per order {max_margin_per_order:.8f}")
            # Корректируем объем
            adjusted_volume = (max_margin_per_order / price) / (1 + MAKER_COMMISSION_RATE)
            print(f"Adjusting volume from {volume:.8f} to {adjusted_volume:.8f}")
            volume = adjusted_volume
            total_required = price * volume * (1 + MAKER_COMMISSION_RATE)

        # Последняя проверка перед размещением
        if price > 0 and self.free_margin >= total_required:
            order = Order(order_type, price, volume, MAKER_COMMISSION_RATE)
            self.orders.append(order)
            old_free_margin = self.free_margin
            self.free_margin -= total_required
            logger.info(
                f"[MARGIN_DEBUG] После размещения ордера {order_type}: изменение маржи={-total_required:.8f}, новая свободная маржа={self.free_margin:.8f}"
            )
            print(f"Order placed successfully. Remaining margin: {self.free_margin:.8f}")
            return True
        else:
            print(f"ERROR: Not enough margin to place {order_type} order!")
            print(f"Required: {total_required:.8f}, Available: {self.free_margin:.8f}")
            return False

    def create_asymmetric_grid(self, ema, current_price, lower_bound, upper_bound, buy_step, sell_step):
        """Создание асимметричной сетки ордеров"""
        print(f"Creating grid: price={current_price}, lower={lower_bound}, upper={upper_bound}")

        buy_prices = []
        current_price_buy = ema
        while current_price_buy > lower_bound and len(buy_prices) < self.max_orders:
            next_price = current_price_buy * (1 - buy_step / 100)
            if next_price >= lower_bound:
                buy_prices.append(next_price)
                current_price_buy = next_price
            else:
                break

        sell_prices = []
        current_price_sell = ema
        while current_price_sell < upper_bound and len(sell_prices) < self.max_orders:
            next_price = current_price_sell * (1 + sell_step / 100)
            if next_price <= upper_bound:
                sell_prices.append(next_price)
                current_price_sell = next_price
            else:
                break

        print(f"Generated {len(buy_prices)} buy prices and {len(sell_prices)} sell prices")
        return buy_prices, sell_prices

    def update_existing_orders(self, ema, current_price):
        for order in self.orders:
            if not order.executed:
                if order.order_type == "buy" and order.price > current_price:
                    new_price = min(order.price, ema * (1 - self.grid_step_percent / 100))
                    order.price = new_price
                    # print(f"Updated buy order {order.id} price to {new_price}")
                elif order.order_type == "sell" and order.price < current_price:
                    new_price = max(order.price, ema * (1 + self.grid_step_percent / 100))
                    order.price = new_price
                    # print(f"Updated sell order {order.id} price to {new_price}")

    def close_all_positions_at_market(self, market_price):
        """Закрывает все открытые ордера по рыночной цене"""
        closed_profit = 0

        for order in self.orders:
            if not order.executed:
                continue

            # Если ордер исполнен, фиксируем P&L по текущей цене
            if order.order_type == "buy":
                profit = (market_price - order.price) * order.volume
            else:  # sell
                profit = (order.price - market_price) * order.volume

            closed_profit += profit

            # Закрываем ордер, удаляя его из активных
            order.closed = True
            order.closing_price = market_price

            # Можно сохранить в историю закрытых, если нужно
            self.order_history.append(order)

        # Очищаем список активных ордеров
        self.orders = [order for order in self.orders if not order.executed or order.closed]

        # Добавляем прибыль/убыток к балансу
        self.balance += closed_profit
        self.free_margin = self.balance  # После закрытия всех позиций маржа становится свободной

        print(f"Closed all positions at market price {market_price:.4f}, Profit: {closed_profit:.4f}")

        return closed_profit

    def trigger_hedge(self, market_price):
        print(f"Hedge triggered at price {market_price:.4f}")

        estimated_volume = self.estimate_grid_volume()
        hedge_compensation, _ = self.options_manager.calculate_hedge_payout(market_price, estimated_volume)

        profit_from_closing = self.close_all_positions_at_market(market_price)

        self.hedge_active = False

        self.balance += hedge_compensation
        self.free_margin = self.balance

        print(f"Hedge executed. Compensation: {hedge_compensation:.4f}, P&L from closing: {profit_from_closing:.4f}")

        # После хеджа сбрасываем сетку
        self.orders = []
        # Пересчитываем маржу после создания новой сетки
        self.calculate_free_margin()
        self.initialize_new_grid(market_price)

        # Пересчитываем маржу после создания новой сетки
        self.calculate_free_margin()

    def calculate_base_volume(self, current_price):
        """Расчет базового объема с учетом оптимального распределения маржи для долгосрочной торговли"""
        # Общий объем для 160 потенциальных ордеров
        total_potential_orders = 160

        # Рассчитываем базовый объем для одного ордера, используя только 30% свободной маржи
        # чтобы оставить запас для будущих ордеров и контр-ордеров
        margin_for_grid = self.free_margin * 0.30

        # Средняя цена для расчета (можно использовать EMA or текущую цену)
        avg_price = self.current_ema if self.current_ema else current_price

        # Вычисляем базовый объем
        base_volume = margin_for_grid / (total_potential_orders * avg_price)

        # Устанавливаем минимальный объем для надежности
        min_base_volume = 0.1

        # Логируем расчет объема
        logger = logging.getLogger("grid_visualizer")
        logger.debug(
            f"[VOLUME] Расчет объема: маржа={self.free_margin:.4f}, для сетки={margin_for_grid:.4f}, "
            + f"цена={avg_price:.4f}, объем={base_volume:.4f}"
        )

        # Если маржа слишком низкая, отмечаем это, но продолжаем с минимальным объемом
        if base_volume < MIN_VOLUME_THRESHOLD:
            self.low_margin_triggered = True
            logger.warning(f"[VOLUME] Низкая маржа, используем минимальный объем: {min_base_volume}")
        else:
            self.low_margin_triggered = False

        # Берем максимум из рассчитанного и минимального объема
        return max(base_volume, min_base_volume)

    def calculate_order_volume(self, current_price):
        # Рассчитываем общий объем для всей сетки
        total_volume = self.free_margin * 0.5 / current_price  # Используем 50% свободной маржи для всей сетки

        # Делим общий объем на количество уровней сетки
        volume_per_level = total_volume / (self.grid_size * 2)  # Умножаем на 2, так как у нас buy and sell ордера

        return volume_per_level

    def sync_orders_with_virtual_grid(self):
        """Синхронизирует реальные ордера с виртуальной сеткой"""
        if not self.virtual_grid or not self.current_ema or not self.current_price:
            return

        active_orders = {order.price: order for order in self.orders if not order.executed}
        base_volume = self.calculate_base_volume(self.current_price)

        # Buy
        for price in self.virtual_grid["buy"]:
            if price not in active_orders and price < self.current_price and price < self.current_ema:
                self.place_order("buy", price, base_volume)

        # Sell
        for price in self.virtual_grid["sell"]:
            if price not in active_orders and price > self.current_price and price > self.current_ema:
                self.place_order("sell", price, base_volume)

    def place_counter_order(self, executed_order, execution_price):
        """Размещение контр-ордера после исполнения и закрытие соответствующей позиции"""
        if not self.current_grid_bounds:
            print("Error: No grid bounds set")
            return

        lower_bound, upper_bound = self.current_grid_bounds
        grid_step = self.calculate_dynamic_grid_step("sell" if executed_order.order_type == "buy" else "buy")
        volume = executed_order.volume

        # Определяем уровень сетки для исполненного ордера
        if self.current_ema:
            if executed_order.order_type == "buy":
                grid_level = round(
                    (self.current_ema - executed_order.price) / (self.current_ema * (self.grid_step_percent / 100))
                )
            else:
                grid_level = round(
                    (executed_order.price - self.current_ema) / (self.current_ema * (self.grid_step_percent / 100))
                )
        else:
            grid_level = 1

        logger = logging.getLogger("grid_visualizer")
        logger.info(
            f"[GRID_MATH] Creating counter order for {executed_order.order_type} order, volume={volume:.8f}, price={execution_price:.8f}, level={grid_level}"
        )

        # Текущий оставшийся объем для закрытия
        remaining_volume = volume
        total_profit = 0
        total_released_margin = 0

        # Находим все позиции с противоположным типом ордера
        matching_positions = [p for p in self.positions if p.order_type != executed_order.order_type and not p.closed]

        # Логируем состояние до закрытия позиций
        open_buy_pos = [p for p in self.positions if p.order_type == "buy" and not p.closed]
        open_sell_pos = [p for p in self.positions if p.order_type == "sell" and not p.closed]
        logger.info(
            f"[GRID_MATH] Before closing - Buy positions: {len(open_buy_pos)}, Sell positions: {len(open_sell_pos)}"
        )
        logger.info(f"[GRID_MATH] Matching positions to close: {len(matching_positions)}, needed volume: {volume:.8f}")

        # Если есть позиции для закрытия
        if matching_positions:
            # Вычисляем расстояние от каждой позиции до EMA для определения их уровня
            for position in matching_positions:
                if self.current_ema:
                    if position.order_type == "buy":
                        position.grid_level = round(
                            (self.current_ema - position.entry_price)
                            / (self.current_ema * (self.grid_step_percent / 100))
                        )
                    else:
                        position.grid_level = round(
                            (position.entry_price - self.current_ema)
                            / (self.current_ema * (self.grid_step_percent / 100))
                        )
                else:
                    position.grid_level = 1

            # Сортируем позиции по близости уровня к уровню исполненного ордера
            matching_positions.sort(key=lambda p: abs(getattr(p, "grid_level", 1) - grid_level))

            # Закрываем позиции, пока не израсходуем весь объем
            positions_to_remove = []

            for position in matching_positions:
                if remaining_volume <= 0.000001:
                    break

                close_volume = min(position.volume, remaining_volume)
                position_ratio = close_volume / position.volume
                position_level = getattr(position, "grid_level", 1)

                logger.info(
                    f"[POSITION] Closing position: {position.order_type}, entry={position.entry_price:.8f}, "
                    f"volume={position.volume:.8f}, close_volume={close_volume:.8f}, level={position_level}"
                )

                # ИСПРАВЛЕНИЕ: Всегда закрываем позиции полностью, даже если требуется закрыть только часть
                # Это предотвратит одновременное существование позиций buy и sell
                profit, released_margin = position.close_position(execution_price)

                # Корректируем profit и released_margin в соответствии с долей закрытия
                if position_ratio < 0.999:
                    profit = profit * position_ratio
                    released_margin = released_margin * position_ratio

                total_profit += profit
                total_released_margin += released_margin

                positions_to_remove.append(position)
                self.closed_positions.append(position)

                logger.info(
                    f"[POSITION] Fully closed position at level {position_level}, profit={profit:.8f}, released_margin={released_margin:.8f}"
                )

                # Уменьшаем оставшийся объем для закрытия
                remaining_volume -= close_volume

            # Удаляем полностью закрытые позиции из списка
            for position in positions_to_remove:
                if position in self.positions:
                    self.positions.remove(position)

            # Обновляем баланс и общую прибыль
            self.balance += total_profit
            self.total_profit += total_profit
            self.free_margin += total_released_margin

            logger.info(
                f"[COUNTER] Total profit from closing: {total_profit:.8f}, released margin: {total_released_margin:.8f}, "
                f"remaining volume: {remaining_volume:.8f}"
            )

            # Проверяем, что все противоположные позиции закрыты
            remaining_opposite_positions = [
                p for p in self.positions if p.order_type != executed_order.order_type and not p.closed
            ]
            if remaining_opposite_positions:
                logger.warning(
                    f"[GRID_MATH] Warning: {len(remaining_opposite_positions)} opposite positions remain open after closing operation"
                )

                # Принудительно закрываем все оставшиеся противоположные позиции
                for position in remaining_opposite_positions:
                    profit, released_margin = position.close_position(execution_price)
                    total_profit += profit
                    total_released_margin += released_margin
                    self.positions.remove(position)
                    self.closed_positions.append(position)
                    logger.warning(
                        f"[GRID_MATH] Forcibly closed remaining position: {position.order_type}, profit={profit:.8f}"
                    )

                # Обновляем баланс после принудительного закрытия
                self.balance += total_profit
                self.total_profit += total_profit
                self.free_margin += total_released_margin

        else:
            self.free_margin += total_released_margin

            logger.info(
                f"[COUNTER] Total profit from closing: {total_profit:.8f}, released margin: {total_released_margin:.8f}, "
                f"remaining volume: {remaining_volume:.8f}"
            )
            logger.info(
                f"[GRID_MATH] No matching positions to close for {executed_order.order_type} order at level {grid_level}"
            )

        # Проверяем, нужно ли создавать встречный ордер для оставшегося объема
        if remaining_volume > 0.000001:
            # ВАЖНО: Проверяем, есть ли уже такой ордер в сетке, чтобы избежать дублирования
            existing_counter_orders = []
            counter_type = "sell" if executed_order.order_type == "buy" else "buy"

            if self.current_ema:
                if counter_type == "sell":
                    counter_price = self.current_ema * (1 + grid_step * grid_level / 100)
                else:
                    counter_price = self.current_ema * (1 - grid_step * grid_level / 100)
            else:
                if counter_type == "sell":
                    counter_price = execution_price * (1 + grid_step / 100)
                else:
                    counter_price = execution_price * (1 - grid_step / 100)

            # Проверяем наличие похожих ордеров в сетке
            active_orders = [order for order in self.orders if not order.executed and order.order_type == counter_type]
            for order in active_orders:
                price_diff = abs(order.price - counter_price) / counter_price
                if price_diff < 0.001:  # Если разница меньше 0.1%
                    existing_counter_orders.append(order)

            if existing_counter_orders:
                # Добавляем объем к существующему ордеру вместо создания нового
                target_order = existing_counter_orders[0]
                old_volume = target_order.volume
                old_price = target_order.price

                # Вычисляем новую средневзвешенную цену
                new_volume = old_volume + remaining_volume
                new_price = (old_price * old_volume + counter_price * remaining_volume) / new_volume

                # Освобождаем маржу от старого ордера
                self.free_margin += old_price * old_volume * (1 + MAKER_COMMISSION_RATE)

                # Обновляем ордер
                target_order.price = new_price
                target_order.volume = new_volume
                target_order.commission = new_price * new_volume * MAKER_COMMISSION_RATE

                # Резервируем маржу для обновленного ордера
                required_margin = new_price * new_volume * (1 + MAKER_COMMISSION_RATE)
                self.free_margin -= required_margin

                logger.info(
                    f"[COUNTER] Updated existing {counter_type} order: from vol={old_volume:.8f} to vol={new_volume:.8f}, price={new_price:.8f}"
                )
            else:
                # Если нет похожих ордеров, создаем новый
                if counter_type == "buy" and counter_price >= lower_bound and counter_price <= self.current_price:
                    logger.info(
                        f"[COUNTER] Placing {counter_type} counter order at level {grid_level}, price={counter_price:.8f}"
                    )
                    self.place_order(counter_type, counter_price, remaining_volume)
                elif counter_type == "sell" and counter_price <= upper_bound and counter_price >= self.current_price:
                    logger.info(
                        f"[COUNTER] Placing {counter_type} counter order at level {grid_level}, price={counter_price:.8f}"
                    )
                    self.place_order(counter_type, counter_price, remaining_volume)

        # Обновляем плавающую прибыль
        self.calculate_floating_profit(self.current_price)

    def check_and_refill_orders(self):
        """Проверка and добавление ордеров, если их недостаточно"""
        if not self.current_grid_bounds:
            return

        active_orders = [order for order in self.orders if not order.executed]
        active_buy_orders = [order for order in active_orders if order.order_type == "buy"]
        active_sell_orders = [order for order in active_orders if order.order_type == "sell"]

        # Если ордеров меньше минимального количества, добавляем новые
        if len(active_buy_orders) < self.min_orders or len(active_sell_orders) < self.min_orders:
            lower_bound, upper_bound = self.current_grid_bounds
            buy_step = self.calculate_dynamic_grid_step("buy")
            sell_step = self.calculate_dynamic_grid_step("sell")

            buy_prices, sell_prices = self.create_asymmetric_grid(
                self.current_ema, self.current_price, lower_bound, upper_bound, buy_step, sell_step
            )

            # Добавляем недостающие ордера
            if len(active_buy_orders) < self.min_orders:
                for i, price in enumerate(buy_prices):
                    if (
                        price < self.current_ema
                        and price < self.current_price
                        and not any(o.price == price for o in active_buy_orders)
                    ):
                        volume = self.base_fixed_volume * (self.volume_growth_factor**i)
                        self.place_order("buy", price, volume)

            if len(active_sell_orders) < self.min_orders:
                for i, price in enumerate(sell_prices):
                    if (
                        price > self.current_ema
                        and price > self.current_price
                        and not any(o.price == price for o in active_sell_orders)
                    ):
                        volume = self.base_fixed_volume * (self.volume_growth_factor**i)
                        self.place_order("sell", price, volume)

    def calculate_hedge_boundaries(self, current_price):
        """
        Расчет границ хеджирования на основе последних ордеров
        """
        active_buy_orders = [order for order in self.orders if not order.executed and order.order_type == "buy"]
        active_sell_orders = [order for order in self.orders if not order.executed and order.order_type == "sell"]

        if active_buy_orders and active_sell_orders:
            lower_bound = min(order.price for order in active_buy_orders)
            upper_bound = max(order.price for order in active_sell_orders)
            print(f"Hedge boundaries from orders: lower={lower_bound:.8f}, upper={upper_bound:.8f}")
        else:
            # Если нет активных ордеров, используем текущую цену как основу
            lower_bound = current_price * (1 - self.grid_step_percent / 100)
            upper_bound = current_price * (1 + self.grid_step_percent / 100)
            print(f"Hedge boundaries from price: lower={lower_bound:.8f}, upper={upper_bound:.8f}")

        return lower_bound, upper_bound

    def check_orders(self, current_price, timestamp):
        """Проверяет and исполняет подходящие ордера с учетом временной метки"""
        executed_any = False
        self.current_price = current_price  # Обновляем текущую цену

        for order in self.orders[:]:  # Копируем список для безопасного удаления элементов
            if not order.executed:
                order_executed = False

                if order.order_type == "buy" and current_price <= order.price:
                    order_executed = self.execute_order(order, current_price, timestamp)
                    if order_executed:
                        self.consecutive_buys += 1
                        self.consecutive_sells = 0
                        executed_any = True

                elif order.order_type == "sell" and current_price >= order.price:
                    order_executed = self.execute_order(order, current_price, timestamp)
                    if order_executed:
                        self.consecutive_sells += 1
                        self.consecutive_buys = 0
                        executed_any = True

        # Если были исполнены ордера, проверяем необходимость обновления сетки
        if executed_any:
            self.grid_check_counter += 1  # Увеличиваем счетчик проверок

            # Проверяем состояние сетки
            if self.check_grid_state():
                # Если нужно обновить сетку
                self.update_grid(self.current_ema, current_price, self.price_history)
            else:
                # Иначе просто добавляем недостающие ордера
                self.check_and_refill_orders()

            # Обновляем маржу and другие показатели
            self.calculate_floating_profit(current_price)
            self.calculate_free_margin()

        return executed_any

    def execute_order(self, order, price, timestamp):
        """Исполняет ордер с сохранением временной метки и уровня сетки"""
        try:
            if not order.executed:
                order.execution_price = price
                order.execution_time = timestamp
                order.executed = True

                # Обновляем статистику скорости сделок
                self.update_trade_speed(order.order_type, timestamp)
                
                # Рассчитываем уровень сетки для ордера относительно EMA
                grid_level = self.calculate_grid_level(order.order_type, order.price)

                # Проверка на дублирующие позиции
                existing_positions = [
                    p
                    for p in self.positions
                    if p.order_type == order.order_type and abs(p.entry_price - order.price) < 0.00001 and not p.closed
                ]

                if existing_positions:
                    logger = logging.getLogger("grid_visualizer")
                    logger.warning(
                        f"[ORDER] Потенциально дублирующиеся позиции для ордера {order.id}, {len(existing_positions)} существующих"
                    )
                    for pos in existing_positions:
                        logger.warning(
                            f"[ORDER] Существующая позиция: type={pos.order_type}, price={pos.entry_price:.8f}, vol={pos.volume:.8f}"
                        )

                # Логирование объемов перед добавлением новой позиции
                logger = logging.getLogger("grid_visualizer")
                open_buy_pos = [p for p in self.positions if p.order_type == "buy" and not p.closed]
                open_sell_pos = [p for p in self.positions if p.order_type == "sell" and not p.closed]
                buy_volume_total = sum(p.volume for p in open_buy_pos)
                sell_volume_total = sum(p.volume for p in open_sell_pos)
                logger.info(
                    f"[VOLUME] Before new position - Buy: {buy_volume_total:.8f}, Sell: {sell_volume_total:.8f}, Diff: {buy_volume_total - sell_volume_total:.8f}"
                )

                # Создаем новую позицию и добавляем к ней информацию об уровне сетки
                position = Position(order.order_type, order.price, order.volume, order.is_maker)
                position.grid_level = grid_level  # Сохраняем уровень сетки для позиции
                self.positions.append(position)

                # Подробно логируем информацию о новой позиции
                logger.info(
                    f"[MARGIN] Position created: {position.order_type}, entry={position.entry_price:.8f}, volume={position.volume:.8f}, margin={position.margin:.8f}, level={grid_level}"
                )

                # Обновляем баланс и комиссию
                self.balance -= order.commission
                self.total_commission += order.commission
                logger.info(f"[BALANCE] Deducted commission: {order.commission:.8f}, New balance: {self.balance:.8f}")

                # Добавляем в историю исполненных ордеров
                self.order_history.append(order)
                self.executed_orders_history.append(order)

                # Логируем исполнение
                logger.info(
                    f"[ORDER] Executed {order.order_type} order at {price:.8f}, "
                    f"time={timestamp}, commission={order.commission:.8f}, level={grid_level}"
                )

                # Сохраняем значение свободной маржи до размещения встречного ордера
                margin_before = self.free_margin
                logger.info(f"[MARGIN] Before counter order - Free margin: {margin_before:.8f}")

                # Размещаем встречный ордер
                self.place_counter_order(order, price)

                # Обновляем свободную маржу
                self.calculate_free_margin()

                # Логируем изменение маржи после всех операций
                margin_after = self.free_margin
                logger.info(
                    f"[MARGIN] After all operations - Free margin: {margin_after:.8f}, Diff: {margin_after - margin_before:.8f}"
                )

                # Проверяем состояние позиций после всех операций
                open_buy_pos_after = [p for p in self.positions if p.order_type == "buy" and not p.closed]
                open_sell_pos_after = [p for p in self.positions if p.order_type == "sell" and not p.closed]
                buy_volume_after = sum(p.volume for p in open_buy_pos_after)
                sell_volume_after = sum(p.volume for p in open_sell_pos_after)
                logger.info(
                    f"[VOLUME] After all operations - Buy: {buy_volume_after:.8f}, Sell: {sell_volume_after:.8f}, Diff: {buy_volume_after - sell_volume_after:.8f}"
                )

                # Добавим аудит уровней сетки для открытых позиций
                level_counts = {}
                for pos in self.positions:
                    if not pos.closed:
                        pos_level = getattr(pos, "grid_level", 0)
                        if pos_level not in level_counts:
                            level_counts[pos_level] = {"buy": 0, "sell": 0}
                        level_counts[pos_level][pos.order_type] += 1

                # Логируем распределение позиций по уровням
                logger.info(f"[GRID_AUDIT] Open positions by levels: {level_counts}")

                return True

        except Exception as e:
            logger = logging.getLogger("grid_visualizer")
            logger.error(f"[ORDER] Error executing order: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())

        return False

    def _check_order_execution(self, current_price):
        """Проверка исполнения ордеров с учетом типа комиссии"""
        last_price = self.price_history[-2] if len(self.price_history) > 1 else current_price
        price_range = sorted([last_price, current_price])

        for order in self.orders[:]:
            if not order.executed:
                if (order.order_type == "buy" and price_range[0] <= order.price <= price_range[1]) or (
                    order.order_type == "sell" and price_range[0] <= order.price <= price_range[1]
                ):
                    # Определяем, является ли ордер мейкером or тейкером
                    is_maker = abs(order.price - current_price) < 0.0001
                    self.execute_order(order, order.price, is_maker)

    def estimate_grid_volume(self):
        """Оценка потенциального объема всей сетки"""
        base_volume = self.calculate_base_volume(self.current_price)
        total_volume = 0

        # Считаем объем для buy and sell сторон
        for i in range(self.max_orders):
            volume = base_volume * (self.volume_growth_factor**i)
            total_volume += volume * 2  # умножаем на 2, так как у нас buy and sell стороны

        print(f"Estimated total grid volume: {total_volume:.8f}")
        return total_volume

    def initialize_new_grid(self, current_price):
        if self.current_ema is None or len(self.price_history) == 0:
            print("Cannot initialize grid: No EMA or price history")
            return

        print(f"\nInitializing new full grid at price {current_price:.8f}")

        # Перестраиваем сетку как в самом начале, ± max_orders шагов от цены
        lower_bound = self.current_ema * (1 - self.grid_step_percent * self.max_orders / 100)
        upper_bound = self.current_ema * (1 + self.grid_step_percent * self.max_orders / 100)

        self.current_grid_bounds = (lower_bound, upper_bound)
        self._build_virtual_grid()  # создаем виртуальные уровни

        buy_prices, sell_prices = self.create_asymmetric_grid(
            self.current_ema, current_price, lower_bound, upper_bound, self.grid_step_percent, self.grid_step_percent
        )

        buy_prices = buy_prices[: self.max_orders]
        sell_prices = sell_prices[: self.max_orders]

        base_volume = self.calculate_base_volume(self.current_ema)

        for i, price in enumerate((buy_prices)):
            volume = base_volume * (self.volume_growth_factor**i)
            if price < self.current_ema and price < self.current_price:
                self.place_order("buy", price, volume)

        for i, price in enumerate((sell_prices)):
            volume = base_volume * (self.volume_growth_factor**i)
            if price > self.current_ema and price > self.current_price:
                self.place_order("sell", price, volume)

        if len(self.price_history) > 30:
            price_returns = np.diff(np.log(self.price_history[-30:]))
            volatility = np.std(price_returns) * np.sqrt(252)
        else:
            volatility = 0.5

        estimated_volume = self.estimate_grid_volume()

        hedge_position = self.options_manager.create_hedge_strategy(
            current_price, (lower_bound, upper_bound), volatility, estimated_volume
        )

        self.free_margin -= hedge_position["total_cost"]
        self.hedge_active = True

        self.check_and_refill_orders()
        # self.update_display()

        print(f"Created new grid with {len(buy_prices)} buy orders and {len(sell_prices)} sell orders.")

    def _build_virtual_grid(self):
        """Создает виртуальную сетку buy/sell вокруг текущей EMA"""
        self.virtual_grid = {"buy": [], "sell": []}

        grid_step = self.grid_step_percent / 100

        # Buy уровни
        price = self.current_ema
        while price > self.current_grid_bounds[0]:
            price *= 1 - grid_step
            if price < self.current_ema:
                self.virtual_grid["buy"].append(price)

        # Sell уровни
        price = self.current_ema
        while price < self.current_grid_bounds[1]:
            price *= 1 + grid_step
            if price > self.current_ema:
                self.virtual_grid["sell"].append(price)

        self.virtual_grid["buy"].reverse()  # Чтобы buy шли от дальних к ближним

    def get_hedge_metrics(self):
        """
        Получение метрик хеджирования
        """
        return self.options_manager.get_hedge_metrics()

    def calculate_total_position_risk(self, current_price):
        """
        Расчет общего риска позиций с учетом хеджа
        """
        # Риск по открытым позициям
        position_risk = sum(abs(pos.floating_profit) for pos in self.positions)

        # Риск по хеджирующим позициям
        hedge_exposure = self.options_manager.get_current_hedge_exposure(current_price)

        return position_risk - hedge_exposure  # Чистый риск с учетом хеджа

    # def update_display(self):
    #     # Этот метод будет вызывать обновление графика
    #     # Его реализацию нужно добавить в TradingSimulator
    #     pass

    def calculate_dynamic_grid_step(self, order_type):
        """
        Рассчитывает динамический шаг сетки на основе скорости сделок.
        Шаг адаптивно увеличивается при росте скорости сделок и уменьшается при падении.
        Никогда не опускается ниже минимального безопасного значения.
        
        Args:
            order_type: тип ордера ("buy" or "sell")
            
        Returns:
            float: шаг сетки в процентах
        """
        logger = logging.getLogger("grid_visualizer")
        
        # Определяем текущую скорость сделок для заданного типа ордера
        trade_speed = self.buy_trade_speed if order_type == "buy" else self.sell_trade_speed
        
        # Если скорость сделок ещё не измерена (нет истории), используем старый метод
        if trade_speed <= 0.000001:
            if order_type == "buy":
                multiplier = min(2**self.consecutive_buys, self.max_grid_step_multiplier)
            else:  # sell
                multiplier = min(2**self.consecutive_sells, self.max_grid_step_multiplier)
            
            return max(self.base_grid_step * multiplier, self.min_grid_step)
        
        # Вычисляем коэффициент изменения шага на основе отношения текущей скорости к базовой
        speed_ratio = trade_speed / self.base_trade_speed
        
        # Логирование для отладки
        logger.debug(f"[GRID_STEP] {order_type} trade_speed={trade_speed:.6f}, base_speed={self.base_trade_speed:.6f}, ratio={speed_ratio:.2f}")
        
        # Если скорость выше базовой, увеличиваем шаг пропорционально
        if speed_ratio > 1.0:
            # Ограничиваем максимальный множитель
            multiplier = min(speed_ratio, self.max_grid_step_multiplier)
            logger.info(f"[GRID_STEP] Увеличение шага {order_type} из-за высокой скорости сделок: x{multiplier:.2f}")
        # Если скорость ниже базовой, уменьшаем шаг пропорционально, но не ниже минимального
        else:
            # Множитель минимум 0.5 (уменьшение шага не более чем в 2 раза)
            multiplier = max(speed_ratio, 0.5)
            if multiplier < 0.8:  # Если шаг уменьшается более чем на 20%, логируем
                logger.info(f"[GRID_STEP] Уменьшение шага {order_type} из-за низкой скорости сделок: x{multiplier:.2f}")
        
        # Рассчитываем новый шаг и гарантируем, что он не ниже минимального
        grid_step = max(self.base_grid_step * multiplier, self.min_grid_step)
        
        # Если шаг изменился значительно, логируем
        if abs(grid_step - self.base_grid_step) / self.base_grid_step > 0.2:  # Изменение более 20%
            logger.info(f"[GRID_STEP] Новый шаг для {order_type}: {grid_step:.6f}% (базовый: {self.base_grid_step:.6f}%)")
        
        return grid_step

    def print_orders(self):
        print("\nТекущая сетка ордеров:")
        for order in self.orders:
            if not order.executed:
                print(
                    f"{order.order_type.upper()} | Цена: {order.price:.4f} | Объем: {order.volume:.4f} | ID: {order.id}"
                )

    def initialize_grid(self):
        """Инициализация первоначальной торговой сетки"""
        # Проверяем, разрешено ли создание ордеров and не создана ли уже сетка
        if not self.orders_enabled:
            print("Grid initialization skipped: orders not enabled")
            return

        if self.initial_grid_created:
            print("Grid already initialized")
            return

        if not self.current_price or not self.current_ema:
            print("Cannot initialize grid: No price or EMA data")
            return

        print(f"Initializing grid at price {self.current_price}, EMA: {self.current_ema}")

        # Рассчитываем границы сетки
        lower_bound = self.current_price * (1 - self.grid_step_percent * self.max_orders / 100)
        upper_bound = self.current_price * (1 + self.grid_step_percent * self.max_orders / 100)

        # Сохраняем границы для дальнейшего использования
        self.current_grid_bounds = (lower_bound, upper_bound)

        # Создаем виртуальную сетку
        self._build_virtual_grid()

        # Создаем асимметричную сетку
        buy_prices, sell_prices = self.create_asymmetric_grid(
            self.current_ema,
            self.current_price,
            lower_bound,
            upper_bound,
            self.grid_step_percent,
            self.grid_step_percent,
        )

        # Ограничиваем количество уровней
        buy_prices = buy_prices[: self.max_orders]
        sell_prices = sell_prices[: self.max_orders]

        if not buy_prices or not sell_prices:
            print("Error: Failed to generate grid prices!")
            return

        # Рассчитываем базовый объем с учетом свободной маржи
        base_volume = self.calculate_base_volume(self.current_price)

        # Проверяем, хватает ли маржи для всех ордеров
        total_required_margin = 0

        # Рассчитываем необходимую маржу для ордеров на покупку
        for i, price in enumerate(buy_prices):
            volume = base_volume * (self.volume_growth_factor**i)
            required_margin = price * volume * (1 + MAKER_COMMISSION_RATE)
            total_required_margin += required_margin

        # Рассчитываем необходимую маржу для ордеров на продажу
        for i, price in enumerate(sell_prices):
            volume = base_volume * (self.volume_growth_factor**i)
            required_margin = price * volume * (1 + MAKER_COMMISSION_RATE)
            total_required_margin += required_margin

        # Если требуемая маржа превышает доступную, корректируем объем
        if total_required_margin > self.free_margin * 0.8:  # Используем не более 80% свободной маржи
            adjustment_factor = (self.free_margin * 0.8) / total_required_margin
            base_volume *= adjustment_factor
            print(f"Adjusted base volume to {base_volume:.8f} due to margin constraints")

        # Размещаем ордера
        orders_placed = 0

        # Размещаем ордера на покупку
        for i, price in enumerate(buy_prices):
            if orders_placed >= self.max_orders:
                break

            volume = base_volume * (self.volume_growth_factor**i)
            if price < self.current_ema:
                if self.place_order("buy", price, volume):
                    orders_placed += 1

        # Размещаем ордера на продажу
        for i, price in enumerate(sell_prices):
            if orders_placed >= self.max_orders * 2:  # Лимит на общее количество ордеров
                break

            volume = base_volume * (self.volume_growth_factor**i)
            if price > self.current_ema:
                if self.place_order("sell", price, volume):
                    orders_placed += 1

        # Хеджирование (опционально)
        if len(self.price_history) > 30:
            price_returns = np.diff(np.log(self.price_history[-30:]))
            volatility = np.std(price_returns) * np.sqrt(252)
        else:
            volatility = 0.5

        # Создаем хедж только если маржа позволяет
        estimated_volume = self.estimate_grid_volume()
        hedge_position = self.options_manager.create_hedge_strategy(
            self.current_price, (lower_bound, upper_bound), volatility, estimated_volume
        )

        # Проверяем, хватает ли маржи для хеджа
        if hedge_position["total_cost"] < self.free_margin * 0.2:  # Не более 20% от свободной маржи на хедж
            self.free_margin -= hedge_position["total_cost"]
            self.hedge_active = True
        else:
            print(
                f"WARNING: Not enough margin for hedge. Required: {hedge_position['total_cost']:.8f}, Available: {self.free_margin * 0.2:.8f}"
            )

        # Проверяем and дополняем ордера, если необходимо
        self.check_and_refill_orders()

        # Выводим информацию о текущей сетке
        self.print_orders()

        # Устанавливаем флаг, что начальная сетка создана
        self.initial_grid_created = True

        print(f"Grid initialized with {orders_placed} orders. Free margin: {self.free_margin:.8f}")

    def should_update_grid(self, executed_order):
        # Определение, нужно ли обновлять сетку на основе условий исполнения ордера
        # Например, можно проверить, достиг ли рынок определенных критериев or настроек
        return True  # По умолчанию всегда обновлять после исполнения

    def calculate_total_commission(self):
        total_commission = sum(order.commission for order in self.executed_orders)
        total_commission += sum(
            order.volume * order.price * order.commission_rate for order in self.orders if not order.executed
        )
        return total_commission

    def update_balance(self):
        """
        Обновление баланса.
        Баланс = Начальный баланс + Прибыль закрытых позиций - Комиссии
        """
        self.balance = self.initial_balance + self.total_profit - self.total_commission
        # print(f"\nBalance updated:")
        # print(f"Initial balance: {self.initial_balance:.8f}")
        # print(f"Total profit: {self.total_profit:.8f}")
        # print(f"Total commission: {self.total_commission:.8f}")
        # print(f"Current balance: {self.balance:.8f}")
        return self.balance

    def calculate_free_margin(self):
        """
        Расчет свободной маржи с учетом всех открытых позиций и ордеров
        Free Margin = Balance - Used Margin (positions) - Used Margin (orders)
        """
        # Важно: плавающая прибыль НЕ увеличивает свободную маржу, чтобы избежать каскадной ликвидации!

        logger = logging.getLogger("grid_visualizer")

        previous_free_margin = self.free_margin if hasattr(self, "free_margin") else self.initial_balance

        # Маржа используемая открытыми позициями
        margin_used_positions = 0

        # Подробно логируем каждую открытую позицию для анализа
        logger.debug(f"[MARGIN] Подробный расчет маржи по позициям:")
        for pos in self.positions:
            if not pos.closed:
                logger.debug(
                    f"[MARGIN] Позиция {pos.order_type}, цена={pos.entry_price:.8f}, объем={pos.volume:.8f}, маржа={pos.margin:.8f}"
                )
                if pos.margin < 0:
                    logger.warning(
                        f"[MARGIN] Обнаружена отрицательная маржа: {pos.margin:.8f} в позиции {pos.order_type}"
                    )
                margin_used_positions += pos.margin

        # Маржа зарезервированная под открытые ордера
        margin_used_orders = 0

        # Подробно логируем каждый открытый ордер
        logger.debug(f"[MARGIN] Подробный расчет маржи по ордерам:")
        order_count = 0
        for order in self.orders:
            if not order.executed:
                order_margin = order.price * order.volume
                logger.debug(
                    f"[MARGIN] Ордер {order.id}, тип={order.order_type}, цена={order.price:.8f}, объем={order.volume:.8f}, маржа={order_margin:.8f}"
                )
                margin_used_orders += order_margin
                order_count += 1

        logger.debug(f"[MARGIN] Общее количество открытых ордеров: {order_count}")

        # Комиссия за открытые ордера
        commission_orders = sum(order.commission for order in self.orders if not order.executed)

        # Проверяем корректность баланса
        if self.balance < 0:
            logger.warning(f"[MARGIN] Обнаружен отрицательный баланс: {self.balance:.8f}")

        # Рассчитываем свободную маржу
        free_margin_calculated = self.balance - margin_used_positions - margin_used_orders - commission_orders

        # Проверяем, не изменилась ли свободная маржа значительно
        if abs(free_margin_calculated - previous_free_margin) > 0.01 * self.initial_balance:
            logger.warning(
                f"[MARGIN_CHANGE] Значительное изменение свободной маржи: с {previous_free_margin:.8f} до {free_margin_calculated:.8f}"
            )
            logger.warning(f"[MARGIN_CHANGE] Разница: {free_margin_calculated - previous_free_margin:.8f}")
            logger.warning(
                f"[MARGIN_CHANGE] Причины изменения - Позиции: {margin_used_positions:.8f}, Ордера: {margin_used_orders:.8f}, Комиссии: {commission_orders:.8f}"
            )

        # Обновляем свободную маржу
        self.free_margin = free_margin_calculated

        # Проверяем корректность свободной маржи
        if self.free_margin < 0:
            logger.warning(f"[MARGIN] Критически низкая свободная маржа: {self.free_margin:.8f}")
        elif self.free_margin < 0.1 * self.initial_balance:
            logger.warning(
                f"[MARGIN] Потенциально опасно низкая свободная маржа: {self.free_margin:.8f} (менее 10% от начальной)"
            )

        # Подробная информация о балансе и марже
        logger.debug(
            f"[MARGIN] Balance: {self.balance:.8f}, "
            f"Used by positions: {margin_used_positions:.8f}, "
            f"Used by orders: {margin_used_orders:.8f}, "
            f"Commission: {commission_orders:.8f}, "
            f"Free margin: {self.free_margin:.8f}"
        )

        # Вычисляем маржинальность как отношение свободной маржи к начальному балансу
        margin_ratio = self.free_margin / self.initial_balance if self.initial_balance > 0 else 0
        logger.debug(f"[MARGIN_RATIO] Текущая маржинальность: {margin_ratio:.2%} от начального баланса")

        # Проверяем согласованность объемов открытых позиций
        open_buy_pos = [p for p in self.positions if p.order_type == "buy" and not p.closed]
        open_sell_pos = [p for p in self.positions if p.order_type == "sell" and not p.closed]
        buy_volume = sum(p.volume for p in open_buy_pos)
        sell_volume = sum(p.volume for p in open_sell_pos)
        volume_diff = buy_volume - sell_volume

        if abs(volume_diff) > 0.1:  # Если разница в объемах превышает 0.1
            logger.warning(
                f"[GRID_MATH] Несбалансированность объемов позиций! Buy: {buy_volume:.8f}, Sell: {sell_volume:.8f}, Diff: {volume_diff:.8f}"
            )

        return self.free_margin

    def get_order_history(self):
        return self.order_history

    def get_open_positions(self):
        """Возвращает список открытых позиций"""
        return [pos for pos in self.positions if not pos.closed]

    def get_closed_positions(self):
        """Возвращает список закрытых позиций"""
        return self.closed_positions

    def get_open_orders_count(self):
        """Возвращает количество активных (неисполненных) ордеров"""
        return len([order for order in self.orders if not order.executed])

    def get_total_trades_count(self):
        """Возвращает общее количество завершенных сделок"""
        return len(self.closed_positions) + len(self.executed_orders_history)

    def calculate_floating_profit(self, current_price):
        """Пересчитывает плавающую прибыль для всех открытых позиций"""
        total_floating_profit = 0
        for position in self.positions:
            if not position.closed:
                floating_profit = position.update_floating_profit(current_price)
                total_floating_profit += floating_profit

        # Обновляем общую плавающую прибыль
        self.floating_profit = total_floating_profit
        return total_floating_profit

    def get_total_profit(self):
        self.total_profit = sum(position.profit for position in self.closed_positions)
        return self.total_profit

    def get_total_commission(self):
        self.total_commission = sum(position.commission for position in self.closed_positions)
        return self.total_commission

    def get_balance(self):
        self.update_balance()
        return self.balance

    def get_floating_profit(self):
        return self.floating_profit

    def get_free_margin(self):
        self.calculate_free_margin()
        return self.free_margin

    def clear_orders(self):
        self.orders = []
        self.executed_orders = []
        self.order_history = []
        self.profit = 0
        self.floating_profit = 0
        self.balance = self.initial_balance
        self.free_margin = self.initial_balance
        # print("All orders cleared and balance reset")

    def place_grid_orders(self, buy_prices, sell_prices, volume):
        for price in buy_prices:
            self.place_order("buy", price, volume)
        for price in sell_prices:
            self.place_order("sell", price, volume)

    def calculate_grid_level(self, order_type, price):
        """Рассчитывает уровень сетки для ордера относительно EMA"""
        if not self.current_ema:
            return 1  # По умолчанию, если EMA не определена

        # Вычисляем расстояние от цены до EMA в процентах
        distance = abs(price - self.current_ema) / self.current_ema

        # Переводим расстояние в уровни сетки (целое число)
        grid_level = round(distance / (self.grid_step_percent / 100))

        # Минимальный уровень - 1
        grid_level = max(1, grid_level)

        logger = logging.getLogger("grid_visualizer")
        logger.debug(f"[GRID_LEVEL] {order_type} price={price:.4f}, ema={self.current_ema:.4f}, level={grid_level}")

        return grid_level

    def close_distant_orders(self, current_ema, max_distance=10):
        """
        Закрывает ордера и позиции, которые находятся слишком далеко от текущего значения EMA

        Args:
            current_ema: текущее значение EMA
            max_distance: максимальное количество уровней от EMA, после которого ордера закрываются
        """
        logger = logging.getLogger("grid_visualizer")

        # Получаем все активные ордера и позиции
        buy_orders = list(self.buy_orders.values())
        sell_orders = list(self.sell_orders.values())
        buy_positions = list(self.buy_positions.values())
        sell_positions = list(self.sell_positions.values())

        closed_orders_count = 0
        closed_positions_count = 0

        # Закрываем buy ордера, которые слишком далеко ниже EMA
        for order in buy_orders:
            # Рассчитываем расстояние от ордера до EMA в процентах
            price_diff_percent = (current_ema - order.price) / current_ema * 100
            levels_away = abs(price_diff_percent) / self.grid_step

            if levels_away > max_distance:
                logger.info(
                    f"[GRID_CLEANUP] Закрытие удаленного buy ордера: цена={order.price:.8f}, "
                    + f"EMA={current_ema:.8f}, уровней={levels_away:.2f} > {max_distance}"
                )

                # Закрываем ордер
                self.cancel_order(order.order_id)
                closed_orders_count += 1

        # Закрываем sell ордера, которые слишком далеко выше EMA
        for order in sell_orders:
            # Рассчитываем расстояние от ордера до EMA в процентах
            price_diff_percent = (order.price - current_ema) / current_ema * 100
            levels_away = abs(price_diff_percent) / self.grid_step

            if levels_away > max_distance:
                logger.info(
                    f"[GRID_CLEANUP] Закрытие удаленного sell ордера: цена={order.price:.8f}, "
                    + f"EMA={current_ema:.8f}, уровней={levels_away:.2f} > {max_distance}"
                )

                # Закрываем ордер
                self.cancel_order(order.order_id)
                closed_orders_count += 1

        # Закрываем buy позиции, которые слишком далеко ниже EMA
        for position in buy_positions:
            # Рассчитываем расстояние от позиции до EMA в процентах
            price_diff_percent = (current_ema - position.entry_price) / current_ema * 100
            levels_away = abs(price_diff_percent) / self.grid_step

            if levels_away > max_distance:
                logger.info(
                    f"[GRID_CLEANUP] Закрытие удаленной buy позиции: вход={position.entry_price:.8f}, "
                    + f"EMA={current_ema:.8f}, уровней={levels_away:.2f} > {max_distance}"
                )

                # Закрываем позицию по рыночной цене
                self.close_position_market(position.position_id)
                closed_positions_count += 1

        # Закрываем sell позиции, которые слишком далеко выше EMA
        for position in sell_positions:
            # Рассчитываем расстояние от позиции до EMA в процентах
            price_diff_percent = (position.entry_price - current_ema) / current_ema * 100
            levels_away = abs(price_diff_percent) / self.grid_step

            if levels_away > max_distance:
                logger.info(
                    f"[GRID_CLEANUP] Закрытие удаленной sell позиции: вход={position.entry_price:.8f}, "
                    + f"EMA={current_ema:.8f}, уровней={levels_away:.2f} > {max_distance}"
                )

                # Закрываем позицию по рыночной цене
                self.close_position_market(position.position_id)
                closed_positions_count += 1

        if closed_orders_count > 0 or closed_positions_count > 0:
            logger.warning(
                f"[GRID_CLEANUP] Закрыто удаленных ордеров: {closed_orders_count}, позиций: {closed_positions_count}"
            )

        return closed_orders_count, closed_positions_count

    def close_distant_orders(self, max_distance=10):
        """
        Закрывает ордера, находящиеся дальше указанного количества уровней от EMA

        Args:
            max_distance: Максимальное расстояние от EMA в уровнях сетки

        Returns:
            Количество закрытых ордеров
        """
        if not self.current_ema:
            return 0

        logger = logging.getLogger("grid_visualizer")
        logger.info(f"[GRID] Проверка дальних ордеров, макс. расстояние={max_distance} уровней")

        closed_count = 0
        orders_to_remove = []

        # Проверяем все активные ордера
        for order in self.orders:
            if not order.executed:
                # Рассчитываем уровень сетки для ордера
                grid_level = self.calculate_grid_level(order.order_type, order.price)

                # Если уровень превышает максимальное расстояние, закрываем ордер
                if grid_level > max_distance:
                    logger.info(
                        f"[GRID] Закрытие удаленного ордера: {order.order_type}, price={order.price:.4f}, level={grid_level}"
                    )

                    # Возвращаем маржу
                    released_margin = order.price * order.volume * (1 + MAKER_COMMISSION_RATE)
                    self.free_margin += released_margin

                    orders_to_remove.append(order)
                    closed_count += 1

        # Удаляем закрытые ордера из списка
        for order in orders_to_remove:
            self.orders.remove(order)

        if closed_count > 0:
            logger.info(f"[GRID] Закрыто {closed_count} удаленных ордеров, освобождено маржи: {self.free_margin:.4f}")

        return closed_count

    def optimize_grid(self, current_price):
        """
        Оптимизирует сетку ордеров для соответствия требованиям:
        - Хватало на 160 потенциальных ордеров
        - Активными оставались только 10 ближайших к EMA

        Args:
            current_price: Текущая цена

        Returns:
            bool: True если сетка была оптимизирована
        """
        if not self.current_ema:
            return False

        logger = logging.getLogger("grid_visualizer")
        logger.info(f"[GRID] Оптимизация сетки ордеров при EMA={self.current_ema:.4f}")

        # 1. Закрываем дальние ордера (больше 10 уровней от EMA)
        closed_count = self.close_distant_orders(10)

        # 2. Проверяем, хватает ли у нас активных ордеров рядом с EMA
        active_buy_orders = [order for order in self.orders if not order.executed and order.order_type == "buy"]
        active_sell_orders = [order for order in self.orders if not order.executed and order.order_type == "sell"]

        # Сортируем ордера по расстоянию от EMA
        active_buy_orders.sort(key=lambda o: abs(o.price - self.current_ema))
        active_sell_orders.sort(key=lambda o: abs(o.price - self.current_ema))

        # 3. Проверяем, нужно ли добавить ордера у EMA
        min_orders_per_side = 5  # Минимальное количество ордеров с каждой стороны

        # Если у нас меньше ордеров, чем требуется, добавляем новые
        if len(active_buy_orders) < min_orders_per_side or len(active_sell_orders) < min_orders_per_side:
            logger.info(f"[GRID] Недостаточно ордеров: buy={len(active_buy_orders)}, sell={len(active_sell_orders)}")

            # Рассчитываем оптимальный объем для новых ордеров
            base_volume = self.calculate_optimal_volume(current_price)

            # Добавляем недостающие ордера на покупку
            if len(active_buy_orders) < min_orders_per_side:
                needed_buy = min_orders_per_side - len(active_buy_orders)
                logger.info(f"[GRID] Добавление {needed_buy} buy ордеров")

                # Определяем, каких уровней не хватает
                existing_levels = set(self.calculate_grid_level("buy", order.price) for order in active_buy_orders)
                missing_levels = [i for i in range(1, min_orders_per_side + 1) if i not in existing_levels]

                # Добавляем ордера на недостающие уровни
                for level in missing_levels[:needed_buy]:
                    price = self.current_ema * (1 - (self.grid_step_percent / 100) * level)
                    volume = base_volume * (1.05 ** (level - 1))  # Увеличиваем объем для более дальних уровней

                    # Проверяем, что цена ниже EMA
                    if price < self.current_ema and price < current_price:
                        self.place_order("buy", price, volume)
                        logger.info(f"[GRID] Добавлен buy ордер: price={price:.4f}, vol={volume:.4f}, level={level}")

            # Добавляем недостающие ордера на продажу
            if len(active_sell_orders) < min_orders_per_side:
                needed_sell = min_orders_per_side - len(active_sell_orders)
                logger.info(f"[GRID] Добавление {needed_sell} sell ордеров")

                # Определяем, каких уровней не хватает
                existing_levels = set(self.calculate_grid_level("sell", order.price) for order in active_sell_orders)
                missing_levels = [i for i in range(1, min_orders_per_side + 1) if i not in existing_levels]

                # Добавляем ордера на недостающие уровни
                for level in missing_levels[:needed_sell]:
                    price = self.current_ema * (1 + (self.grid_step_percent / 100) * level)
                    volume = base_volume * (1.05 ** (level - 1))  # Увеличиваем объем для более дальних уровней

                    # Проверяем, что цена выше EMA
                    if price > self.current_ema and price > current_price:
                        self.place_order("sell", price, volume)
                        logger.info(f"[GRID] Добавлен sell ордер: price={price:.4f}, vol={volume:.4f}, level={level}")

            return True

        return closed_count > 0  # Считаем сетку оптимизированной, если были закрыты дальние ордера

    def calculate_optimal_volume(self, price, current_balance, target_orders_count=160, active_orders_count=20):
        """
        Рассчитывает оптимальный объем для ордеров, чтобы маржи хватило на указанное количество ордеров

        Args:
            price: текущая цена
            current_balance: текущий баланс
            target_orders_count: целевое количество ордеров, на которое должно хватить маржи (по умолчанию 160)
            active_orders_count: количество активных ордеров (по умолчанию 20 - по 10 с каждой стороны)

        Returns:
            float: оптимальный объем для ордеров
        """
        logger = logging.getLogger("grid_visualizer")

        # Расчет маржинальных требований для одного ордера
        # Предполагаем, что для ордера нужно около 1% от его стоимости в качестве маржи
        margin_requirement_percent = 0.01

        # Маржа, которую мы хотим зарезервировать для активных ордеров
        margin_for_active_orders = current_balance * 0.2  # 20% баланса для активных ордеров

        # Маржа, которую мы оставляем в запасе (чтобы система не использовала всю маржу)
        margin_reserve = current_balance * 0.3  # 30% баланса в резерве

        # Доступная маржа для ордеров
        available_margin = current_balance - margin_reserve

        # Маржа для каждого активного ордера
        margin_per_active_order = margin_for_active_orders / active_orders_count

        # Максимальный объем для одного ордера, основанный на доступной марже
        max_volume_per_order = margin_per_active_order / (price * margin_requirement_percent)

        # Создаем градацию объемов: ближе к EMA больше объем, дальше - меньше
        base_volume = max_volume_per_order * 0.5  # Базовый объем для самых дальних ордеров

        logger.info(
            f"[VOLUME_CALC] Оптимальный объем рассчитан: {base_volume:.8f} "
            + f"(баланс={current_balance:.2f}, цена={price:.2f}, "
            + f"доступная маржа={available_margin:.2f})"
        )

        return base_volume

    def calculate_optimal_order_volume(self, current_price, max_orders=160, active_orders=10):
        """
        Рассчитывает оптимальный объем для ордеров в сетке

        Args:
            current_price: текущая цена
            max_orders: максимальное количество ордеров, на которые должно хватить маржи
            active_orders: количество активных ордеров с каждой стороны от EMA

        Returns:
            float: оптимальный объем ордера
        """
        logger = logging.getLogger("grid_visualizer")

        # Получаем текущий свободный баланс
        free_margin = self.calculate_free_margin()

        # Рассчитываем средний размер маржи на 1 ордер
        # Оставляем 20% маржи в запасе для колебаний цены
        margin_per_order = (free_margin * 0.8) / max_orders

        # Рассчитываем объем для одного ордера
        # Учитываем, что чем дальше от EMA, тем меньше должен быть объем
        base_volume = margin_per_order / current_price

        # Для ближайших ордеров можем позволить больший объем
        # Например, для первых 10 ордеров с каждой стороны
        base_volume_for_active = base_volume * 2

        logger.info(
            f"[VOLUME_CONTROL] Расчет оптимального объема: свободная маржа={free_margin:.2f}, "
            + f"маржа на ордер={margin_per_order:.2f}, базовый объем={base_volume:.8f}, "
            + f"объем для активных ордеров={base_volume_for_active:.8f}"
        )

        return base_volume_for_active

    def calculate_optimal_volume(self, base_volume, level, max_active_levels=10, total_levels=80):
        """
        Рассчитывает оптимальный объем для ордера в зависимости от уровня и доступной маржи

        Args:
            base_volume: базовый объем ордера (для первого уровня)
            level: уровень ордера относительно EMA (1 - ближайший, и т.д.)
            max_active_levels: максимальное количество активных уровней с каждой стороны
            total_levels: общее количество уровней с каждой стороны, на которые должно хватить маржи

        Returns:
            float: оптимальный объем для данного уровня
        """
        logger = logging.getLogger("grid_visualizer")

        # Если уровень выходит за пределы активных, уменьшаем объем
        if level > max_active_levels:
            # За пределами активных уровней возвращаем 0, так как эти ордера не должны размещаться
            return 0

        # Внутри активных уровней рассчитываем объем с учетом экспоненциального уменьшения
        # Объем уменьшается по мере удаления от EMA
        volume_factor = max(0.5, 1 - (level - 1) * 0.05)  # Уменьшаем объем на 5% с каждым уровнем

        # Ограничиваем объем, чтобы обеспечить равномерное распределение маржи
        # Коэффициент распределения маржи: общая маржа разделена между активными уровнями
        margin_distribution_factor = max_active_levels / total_levels

        # Применяем коэффициенты к базовому объему
        optimal_volume = base_volume * volume_factor * margin_distribution_factor

        logger.debug(
            f"[VOLUME_CALC] Уровень={level}, базовый объем={base_volume:.8f}, "
            + f"фактор объема={volume_factor:.2f}, фактор маржи={margin_distribution_factor:.2f}, "
            + f"итоговый объем={optimal_volume:.8f}"
        )

        return optimal_volume

    def update_ema_and_grid(self, current_price, new_ema):
        """
        Обновляет значение EMA и корректирует сетку ордеров при необходимости

        Args:
            current_price: Текущая цена
            new_ema: Новое значение EMA

        Returns:
            bool: True если сетка была обновлена
        """
        # Проверяем, изменилось ли значение EMA значительно
        significant_change = False

        if self.current_ema is not None:
            # Рассчитываем относительное изменение EMA
            ema_change = abs(new_ema - self.current_ema) / self.current_ema
            significant_change = ema_change > 0.01  # Если изменение больше 1%

        # Обновляем значение EMA
        old_ema = self.current_ema
        self.current_ema = new_ema

        # Если изменение значительное or сетка не инициализирована
        if significant_change or not self.initial_grid_created:
            logger = logging.getLogger("grid_visualizer")
            logger.info(
                f"[GRID] Значительное изменение EMA: {new_ema:.4f} (было {old_ema:.4f if old_ema else 0:.4f}), пересчет сетки"
            )

            # Закрываем ордера, которые слишком далеко от новой EMA
            closed_count = self.close_distant_orders(new_ema, 10)
            logger.info(f"[GRID] Закрыто {closed_count} удаленных ордеров")

            # Рассчитываем оптимальный объем для новых ордеров
            optimal_volume = self.calculate_optimal_volume(
                current_price,
                self.free_margin,
                target_orders_count=160,  # Хотим, чтобы маржи хватило на 160 ордеров
                active_orders_count=20,  # Но активными будут только 20 (по 10 с каждой стороны)
            )

            # Создаем сетку вокруг новой EMA
            lower_bound = new_ema * (1 - self.grid_step_percent * 10 / 100)  # 10 уровней вниз
            upper_bound = new_ema * (1 + self.grid_step_percent * 10 / 100)  # 10 уровней вверх

            # Создаем массивы цен для buy и sell ордеров
            buy_prices = []
            for i in range(1, 11):  # 10 уровней
                price = new_ema * (1 - self.grid_step_percent * i / 100)
                buy_prices.append(price)

            sell_prices = []
            for i in range(1, 11):  # 10 уровней
                price = new_ema * (1 + self.grid_step_percent * i / 100)
                sell_prices.append(price)

            # Размещаем новые ордера с оптимальным объемом
            for i, price in enumerate(buy_prices):
                # Уменьшаем объем для более дальних уровней
                level_volume = optimal_volume * (1 - i * 0.05)  # Уменьшаем на 5% с каждым уровнем
                if price < current_price:  # Размещаем только ниже текущей цены
                    self.place_order("buy", price, level_volume)

            for i, price in enumerate(sell_prices):
                # Уменьшаем объем для более дальних уровней
                level_volume = optimal_volume * (1 - i * 0.05)  # Уменьшаем на 5% с каждым уровнем
                if price > current_price:  # Размещаем только выше текущей цены
                    self.place_order("sell", price, level_volume)

            # Обновляем границы сетки
            self.current_grid_bounds = (lower_bound, upper_bound)

            # Обновляем виртуальную сетку
            self._build_virtual_grid()

            return True

        # Если изменение незначительное, проверяем только наличие нужных ордеров
        elif self.grid_check_counter >= self.grid_check_interval:
            self.grid_check_counter = 0

            # Проверяем, нужно ли добавить недостающие ордера
            active_buy_orders = [order for order in self.orders if not order.executed and order.order_type == "buy"]
            active_sell_orders = [order for order in self.orders if not order.executed and order.order_type == "sell"]

            # Проверяем, есть ли у нас хотя бы 5 ордеров на покупку и продажу
            min_required = 5

            if len(active_buy_orders) < min_required or len(active_sell_orders) < min_required:
                logger = logging.getLogger("grid_visualizer")
                logger.info(
                    f"[GRID] Недостаточно ордеров: buy={len(active_buy_orders)}, sell={len(active_sell_orders)}, добавляю недостающие"
                )

                # Рассчитываем оптимальный объем
                optimal_volume = self.calculate_optimal_volume(
                    current_price, self.free_margin, target_orders_count=160, active_orders_count=10
                )

                # Добавляем недостающие ордера на покупку
                if len(active_buy_orders) < min_required:
                    # Определяем, каких уровней не хватает
                    existing_levels = set()
                    for order in active_buy_orders:
                        level = round((new_ema - order.price) / (new_ema * self.grid_step_percent / 100))
                        existing_levels.add(level)

                    # Добавляем недостающие уровни
                    for level in range(1, 11):
                        if level not in existing_levels and len(active_buy_orders) < min_required:
                            price = new_ema * (1 - self.grid_step_percent * level / 100)
                            if price < current_price:  # Размещаем только ниже текущей цены
                                volume = optimal_volume * (1 - (level - 1) * 0.05)  # Уменьшаем объем с каждым уровнем
                                self.place_order("buy", price, volume)

                # Добавляем недостающие ордера на продажу
                if len(active_sell_orders) < min_required:
                    # Определяем, каких уровней не хватает
                    existing_levels = set()
                    for order in active_sell_orders:
                        level = round((order.price - new_ema) / (new_ema * self.grid_step_percent / 100))
                        existing_levels.add(level)

                    # Добавляем недостающие уровни
                    for level in range(1, 11):
                        if level not in existing_levels and len(active_sell_orders) < min_required:
                            price = new_ema * (1 + self.grid_step_percent * level / 100)
                            if price > current_price:  # Размещаем только выше текущей цены
                                volume = optimal_volume * (1 - (level - 1) * 0.05)  # Уменьшаем объем с каждым уровнем
                                self.place_order("sell", price, volume)

                return True

        return False

    def process_tick(self, current_price, ema_price, timestamp):
        """
        Метод обработки тика цены с оптимизацией сетки и управлением маржой

        Args:
            current_price: текущая цена
            ema_price: текущее значение EMA
            timestamp: временная метка

        Returns:
            bool: True если были исполнены ордера or обновлена сетка
        """
        # Обновляем текущие значения
        self.current_price = current_price

        # Обрабатываем историю цен для аналитики
        self.price_history.append(current_price)
        if len(self.price_history) > 1000:  # Ограничиваем длину истории
            self.price_history = self.price_history[-1000:]

        # Добавляем временную метку
        self.timestamps.append(timestamp)
        if len(self.timestamps) > 1000:
            self.timestamps = self.timestamps[-1000:]

        # Проверяем и исполняем ордера
        executed_orders = self.check_orders(current_price, timestamp)

        # Обновляем плавающую прибыль
        self.calculate_floating_profit(current_price)

        # Увеличиваем счетчик проверок сетки
        self.grid_check_counter += 1

        # Проверяем условия для обновления сетки
        grid_updated = False

        # Обновляем значение EMA и сетку при необходимости
        if ema_price is not None and self.orders_enabled:
            grid_updated = self.update_ema_and_grid(current_price, ema_price)

        # Закрываем удаленные ордера (больше 10 уровней от EMA)
        if self.grid_check_counter >= self.grid_check_interval and ema_price is not None:
            self.grid_check_counter = 0
            if self.close_distant_orders(10) > 0:
                # Если закрыли удаленные ордера, обновляем маржу
                self.calculate_free_margin()
                grid_updated = True

        # Обновляем статистику цен для анализа распределения
        self.update_price_distribution(current_price)

        # Проверяем необходимость хеджирования
        if self.hedge_active:
            self.hedge_counter += 1
            if self.hedge_counter >= self.hedge_update_frequency:
                self.hedge_counter = 0
                # Обновляем хеджирующие позиции
                self.options_manager.update_hedge_positions(current_price)

        # Возвращаем True, если были исполнены ордера or обновлена сетка
        return executed_orders or grid_updated

    def update_trade_speed(self, order_type, timestamp):
        """
        Обновляет скорость сделок для заданного типа ордеров.
        Скорость измеряется в относительном тиковом времени (сделок/тик).
        
        Args:
            order_type: тип ордера ("buy" or "sell")
            timestamp: текущая временная метка (тик)
        """
        logger = logging.getLogger("grid_visualizer")
        
        if order_type == "buy":
            # Рассчитываем время (в тиках) с последней сделки на покупку
            if self.last_buy_trade_tick > 0:
                ticks_since_last_trade = timestamp - self.last_buy_trade_tick
                
                # Добавляем информацию о сделке в историю
                self.buy_trades_history.append([timestamp, ticks_since_last_trade])
                
                # Ограничиваем размер истории
                if len(self.buy_trades_history) > self.trade_speed_window:
                    self.buy_trades_history.pop(0)
                
                # Рассчитываем среднюю скорость сделок (1/среднее время между сделками)
                if len(self.buy_trades_history) > 0:
                    avg_ticks_between_trades = sum(trade[1] for trade in self.buy_trades_history) / len(self.buy_trades_history)
                    if avg_ticks_between_trades > 0:
                        new_speed = 1.0 / avg_ticks_between_trades
                        
                        # Если скорость изменилась значительно, логируем
                        speed_change = abs(new_speed - self.buy_trade_speed) / max(self.buy_trade_speed, 0.0001)
                        if speed_change > 0.3:  # Изменение более чем на 30%
                            logger.info(f"[TRADE_SPEED] Значительное изменение скорости BUY сделок: {self.buy_trade_speed:.6f} -> {new_speed:.6f} (изменение: {speed_change:.2%})")
                        
                        self.buy_trade_speed = new_speed
            
            # Обновляем временную метку последней сделки
            self.last_buy_trade_tick = timestamp
            
        elif order_type == "sell":
            # Рассчитываем время (в тиках) с последней сделки на продажу
            if self.last_sell_trade_tick > 0:
                ticks_since_last_trade = timestamp - self.last_sell_trade_tick
                
                # Добавляем информацию о сделке в историю
                self.sell_trades_history.append([timestamp, ticks_since_last_trade])
                
                # Ограничиваем размер истории
                if len(self.sell_trades_history) > self.trade_speed_window:
                    self.sell_trades_history.pop(0)
                
                # Рассчитываем среднюю скорость сделок (1/среднее время между сделками)
                if len(self.sell_trades_history) > 0:
                    avg_ticks_between_trades = sum(trade[1] for trade in self.sell_trades_history) / len(self.sell_trades_history)
                    if avg_ticks_between_trades > 0:
                        new_speed = 1.0 / avg_ticks_between_trades
                        
                        # Если скорость изменилась значительно, логируем
                        speed_change = abs(new_speed - self.sell_trade_speed) / max(self.sell_trade_speed, 0.0001)
                        if speed_change > 0.3:  # Изменение более чем на 30%
                            logger.info(f"[TRADE_SPEED] Значительное изменение скорости SELL сделок: {self.sell_trade_speed:.6f} -> {new_speed:.6f} (изменение: {speed_change:.2%})")
                        
                        self.sell_trade_speed = new_speed
            
            # Обновляем временную метку последней сделки
            self.last_sell_trade_tick = timestamp
        
        # Логируем текущие скорости, если они изменorсь существенно
        logger.debug(f"[TRADE_SPEED] Текущие скорости сделок: BUY={self.buy_trade_speed:.6f}, SELL={self.sell_trade_speed:.6f}")
        
        return self.buy_trade_speed if order_type == "buy" else self.sell_trade_speed

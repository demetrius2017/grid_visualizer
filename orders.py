import uuid
import numpy as np
from scipy import stats
from options_manager import OptionsManager


# Константы для комиссий Binance
MAKER_COMMISSION_RATE = 0.0002  # 0.02%
TAKER_COMMISSION_RATE = 0.0005  # 0.05%
MIN_VOLUME_THRESHOLD = 0.01


class Position:
    def __init__(self, order_type, price, volume, is_maker=True):
        self.order_type = order_type
        self.entry_price = price
        self.volume = volume
        self.floating_profit = 0
        self.closed = False
        self.exit_price = None
        self.profit = 0
        # Используем соответствующую комиссию в зависимости от типа ордера
        self.commission = price * volume * (MAKER_COMMISSION_RATE if is_maker else TAKER_COMMISSION_RATE)

    def update_floating_profit(self, current_price):
        if self.order_type == "buy":
            self.floating_profit = (current_price - self.entry_price) * self.volume
        else:  # sell
            self.floating_profit = (self.entry_price - current_price) * self.volume
        return self.floating_profit

    def close_position(self, exit_price, is_maker=True):
        self.exit_price = exit_price
        exit_commission = exit_price * self.volume * (MAKER_COMMISSION_RATE if is_maker else TAKER_COMMISSION_RATE)
        total_commission = self.commission + exit_commission

        if self.order_type == "buy":
            self.profit = (exit_price - self.entry_price) * self.volume - total_commission
        else:  # sell
            self.profit = (self.entry_price - exit_price) * self.volume - total_commission
        self.closed = True
        return self.profit


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
        # Существующая инициализация...
        self.options_manager = OptionsManager()
        self.hedge_active = False
        self.hedge_update_frequency = 24 * 60  # Обновление хеджа раз в сутки
        self.hedge_counter = 0
        # Добавляем параметры для периодической проверки =
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


    def check_grid_state(self):
        """Проверка состояния сетки и необходимости её обновления"""
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
        """Простое обновление сетки ордеров: удаляем старые, создаем ровно min_orders вверх и вниз"""
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

        # Нормализуем гистограмму и нормальное распределение
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

        # Рассчитываем расстояние от текущей цены до исторического максимума и минимума
        distance_to_max = (hist_max - current_price) / current_price
        distance_to_min = (current_price - hist_min) / current_price

        # # Устанавливаем верхнюю и нижнюю границы сетки
        # upper_bound = ema * (1 + max(distance_to_min, self.min_grid_coverage))
        # lower_bound = ema * (1 - max(distance_to_max, self.min_grid_coverage))
        # Устанавливаем верхнюю и нижнюю границы сетки
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
        # print(f"\nAttempting to place {order_type} order:")
        # print(f"Price: {price:.8f}")
        # print(f"Volume: {volume:.8f}")

        required_margin = price * volume
        estimated_commission = price * volume * MAKER_COMMISSION_RATE
        total_required = required_margin + estimated_commission

        # Добавляем проверку минимального объема
        min_volume = 0.001  # Минимальный допустимый объем
        if volume < min_volume:
            print(f"ERROR: Volume {volume:.8f} is below minimum {min_volume}")
            return False

        # print(f"Required margin: {required_margin:.8f}")
        # print(f"Estimated commission: {estimated_commission:.8f}")
        # print(f"Free margin available: {self.free_margin:.8f}")

        # Проверяем, не превышает ли требуемая маржа определенный процент от свободной
        max_margin_per_order = self.free_margin * 0.2  # Максимум 20% свободной маржи на один ордер
        if total_required > max_margin_per_order:
            print(f"ERROR: Required margin {total_required:.8f} exceeds max per order {max_margin_per_order:.8f}")
            # Корректируем объем
            adjusted_volume = (max_margin_per_order / price) / (1 + MAKER_COMMISSION_RATE)
            # print(f"Adjusting volume from {volume:.8f} to {adjusted_volume:.8f}")
            volume = adjusted_volume
            total_required = price * volume * (1 + MAKER_COMMISSION_RATE)

        if price > 0 and self.free_margin >= total_required:
            order = Order(order_type, price, volume, MAKER_COMMISSION_RATE)
            self.orders.append(order)
            self.free_margin -= total_required
            # print(f"Order placed successfully. Remaining margin: {self.free_margin:.8f}")
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

        # Выплачиваем условную компенсацию (опцион), например, фиксированную сумму
        estimated_volume = self.estimate_grid_volume()
        hedge_compensation, _ = self.options_manager.calculate_hedge_payout(market_price, estimated_volume)
        # Закрываем все позиции по рыночной цене
        profit_from_closing = self.close_all_positions_at_market(market_price)

        self.hedge_active = False
        # Добавляем компенсацию к балансу
        self.balance += hedge_compensation
        self.free_margin = self.balance  # Все освободилось

        print(f"Hedge executed. Compensation: {hedge_compensation:.4f}, P&L from closing: {profit_from_closing:.4f}")

        # После хеджа сбрасываем сетку
        self.orders = []
        self.initialize_new_grid(market_price)

    def calculate_base_volume(self, current_price):
        """Расчет базового объема с минимальным фиксированным значением"""
        # Используем фиксированный минимальный объем для надежности
        min_base_volume = 10.0

        # Рассчитываем объем на основе свободной маржи
        margin_based_volume = self.free_margin * 0.5 / (self.max_orders * 2 * current_price)

        if margin_based_volume < MIN_VOLUME_THRESHOLD:
            self.low_margin_triggered = True
        else:
            self.low_margin_triggered = False
        # Берем максимум из рассчитанного и минимального объема
        base_volume = max(margin_based_volume, min_base_volume)

        print(f"Calculated base volume: {base_volume:.8f}")
        return base_volume

    def calculate_order_volume(self, current_price):
        # Рассчитываем общий объем для всей сетки
        total_volume = self.free_margin * 0.5 / current_price  # Используем 50% свободной маржи для всей сетки

        # Делим общий объем на количество уровней сетки
        volume_per_level = total_volume / (self.grid_size * 2)  # Умножаем на 2, так как у нас buy и sell ордера

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
        """Размещение контр-ордера после исполнения, с тем же объемом, что был у исполненного"""
        if not self.current_grid_bounds:
            print("Error: No grid bounds set")
            return

        lower_bound, upper_bound = self.current_grid_bounds
        grid_step = self.calculate_dynamic_grid_step("sell" if executed_order.order_type == "buy" else "buy")

        volume = executed_order.volume  # Вот тут фиксируем объем как у исполнившегося ордера

        if executed_order.order_type == "buy":
            new_price = execution_price * (1 + grid_step / 100)
            if new_price <= upper_bound and new_price > self.current_ema and new_price > self.current_price:
                self.place_order("sell", new_price, volume)
            else:
                print(f"Counter sell price {new_price} exceeds upper bound {upper_bound}")
        else:
            new_price = execution_price * (1 - grid_step / 100)
            if new_price >= lower_bound and new_price < self.current_ema and new_price < self.current_price:
                self.place_order("buy", new_price, volume)
            else:
                print(f"Counter buy price {new_price} below lower bound {lower_bound}")

    def check_and_refill_orders(self):
        """Проверка и добавление ордеров, если их недостаточно"""
        if not self.current_grid_bounds:
            return

        active_orders = [order for order in self.orders if not order.executed]
        active_buy_orders = [order for order in active_orders if order.order_type == "buy"]
        active_sell_orders = [order for order in active_orders if order.order_type == "sell"]

        # Если ордеров меньше минимального количества, добавляем новые
        if len(active_buy_orders) < self.min_orders or len(active_sell_orders) < self.min_orders:
            # print("Refilling orders due to low count")
            lower_bound, upper_bound = self.current_grid_bounds
            buy_step = self.calculate_dynamic_grid_step("buy")
            sell_step = self.calculate_dynamic_grid_step("sell")

            buy_prices, sell_prices = self.create_asymmetric_grid(
                self.current_ema, self.current_price, lower_bound, upper_bound, buy_step, sell_step
            )

            # Добавляем недостающие ордера
            base_volume = self.base_fixed_volume * (self.volume_growth_factor**i)
            if len(active_buy_orders) < self.min_orders:
                for i, price in enumerate((buy_prices)):
                    # Проверяем, нет ли уже ордера на этой цене
                    if price < self.current_ema and price < self.current_price and not any(o.price == price for o in active_buy_orders):
                        volume = base_volume * (self.volume_growth_factor**i)
                        self.place_order("buy", price, volume)

            if len(active_sell_orders) < self.min_orders:
                for i, price in enumerate((sell_prices)):
                    if price > self.current_ema and price > self.current_price and not any(o.price == price for o in active_sell_orders):
                        volume = base_volume * (self.volume_growth_factor**i)
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

    def check_orders(self, current_price):
        """Проверка ордеров с улучшенной логикой хеджирования"""
        self.current_price = current_price
        self.calculate_floating_profit(current_price)
        self.calculate_free_margin()
        self.update_price_distribution(current_price)

        active_orders = [order for order in self.orders if not order.executed]
        active_buy_orders = [order for order in active_orders if order.order_type == "buy"]
        active_sell_orders = [order for order in active_orders if order.order_type == "sell"]

        # Независимая проверка условий хеджа
        trigger_hedge = False
        trigger_reason = ""

        last_executed_buy = max(
            (order.execution_price for order in self.order_history if order.executed and order.order_type == "buy"),
            default=None,
        )
        last_executed_sell = min(
            (order.execution_price for order in self.order_history if order.executed and order.order_type == "sell"),
            default=None,
        )

        # Проверка выхода за пределы последних ордеров
        if not active_buy_orders and last_executed_buy is not None and current_price < last_executed_buy:
            trigger_hedge = True
            trigger_reason = f"Price {current_price:.8f} below last executed buy order {last_executed_buy:.8f}"

        if not active_sell_orders and last_executed_sell is not None and current_price > last_executed_sell:
            trigger_hedge = True
            trigger_reason = f"Price {current_price:.8f} above last executed sell order {last_executed_sell:.8f}"

        # Дополнительная проверка границ сетки
        if self.current_grid_bounds:
            lower_bound, upper_bound = self.current_grid_bounds
            if current_price < lower_bound or self.low_margin_triggered:
                trigger_hedge = True
                trigger_reason = f"Price {current_price:.8f} below grid bound {lower_bound:.8f}"
            elif current_price > upper_bound or self.low_margin_triggered:
                trigger_hedge = True
                trigger_reason = f"Price {current_price:.8f} above grid bound {upper_bound:.8f}"

        # Обработка срабатывания хеджа
        if trigger_hedge:
            self.trigger_hedge(current_price)
            # print(f"\nTriggering hedge: {trigger_reason}")
            # estimated_volume = self.estimate_grid_volume()
            # hedge_payout, _ = self.options_manager.calculate_hedge_payout(current_price, estimated_volume)
            # print(f"Hedge payout with estimated volume {estimated_volume:.8f}: {hedge_payout:.8f}")

            # self.balance += hedge_payout

            # margin_returned = sum(
            #     order.volume * order.price * (1 + (MAKER_COMMISSION_RATE if order.is_maker else TAKER_COMMISSION_RATE))
            #     for order in self.orders
            #     if not order.executed
            # )
            # self.free_margin += margin_returned

            # self.orders = [order for order in self.orders if order.executed]

            # self.hedge_active = False

            # print("Initializing new grid...")
            # self.initialize_new_grid(current_price)

            # # ВАЖНО!
            # self.last_grid_time = len(self.price_history)  # Если используешь защиту от частых перестроек

            return  # Останавливаем дальнейшее выполнение метода

        # Проверка исполнения ордеров
        self._check_order_execution(current_price)

    def _check_order_execution(self, current_price):
        """Проверка исполнения ордеров с учетом типа комиссии"""
        last_price = self.price_history[-2] if len(self.price_history) > 1 else current_price
        price_range = sorted([last_price, current_price])

        for order in self.orders[:]:
            if not order.executed:
                if (order.order_type == "buy" and price_range[0] <= order.price <= price_range[1]) or (
                    order.order_type == "sell" and price_range[0] <= order.price <= price_range[1]
                ):
                    # Определяем, является ли ордер мейкером или тейкером
                    is_maker = abs(order.price - current_price) < 0.0001
                    self.execute_order(order, order.price, is_maker)

    def execute_order(self, order, execution_price, is_maker=True):
        """Исполнение ордера с учетом типа комиссии"""
        order.executed = True
        order.execution_price = execution_price
        order.is_maker = is_maker
        order.execution_time = len(self.price_history) - 1
        order.commission = (
            order.volume * execution_price * (MAKER_COMMISSION_RATE if is_maker else TAKER_COMMISSION_RATE)
        )

        opposite_position = next((pos for pos in self.positions if pos.order_type != order.order_type), None)

        if opposite_position:
            profit = opposite_position.close_position(execution_price, is_maker)
            self.total_profit += profit
            self.balance = self.initial_balance + self.total_profit - self.total_commission
            self.closed_positions.append(opposite_position)
            self.positions.remove(opposite_position)
        else:
            new_position = Position(order.order_type, execution_price, order.volume, is_maker)
            self.positions.append(new_position)
            self.total_commission += order.commission

        self.orders.remove(order)
        self.order_history.append(order)
        self.calculate_floating_profit(execution_price)
        self.calculate_free_margin()
        self.place_counter_order(order, execution_price)

    def estimate_grid_volume(self):
        """Оценка потенциального объема всей сетки"""
        base_volume = self.calculate_base_volume(self.current_price)
        total_volume = 0

        # Считаем объем для buy и sell сторон
        for i in range(self.max_orders):
            volume = base_volume * (self.volume_growth_factor**i)
            total_volume += volume * 2  # умножаем на 2, так как у нас buy и sell стороны

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
        self.update_display()

        print(f"Created new grid with {len(buy_prices)} buy orders and {len(sell_prices)} sell orders.")

    def _build_virtual_grid(self):
        """Создает виртуальную сетку buy/sell вокруг текущей EMA"""
        self.virtual_grid = {"buy": [], "sell": []}

        grid_step = self.grid_step_percent / 100

        # Buy уровни
        price = self.current_ema
        while price > self.current_grid_bounds[0]:
            price *= (1 - grid_step)
            if price < self.current_ema:
                self.virtual_grid["buy"].append(price)

        # Sell уровни
        price = self.current_ema
        while price < self.current_grid_bounds[1]:
            price *= (1 + grid_step)
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

    def update_display(self):
        # Этот метод будет вызывать обновление графика
        # Его реализацию нужно добавить в TradingSimulator
        pass

    def calculate_dynamic_grid_step(self, order_type):
        if order_type == "buy":
            multiplier = min(2**self.consecutive_buys, self.max_grid_step_multiplier)
        else:  # sell
            multiplier = min(2**self.consecutive_sells, self.max_grid_step_multiplier)

        return self.base_grid_step * multiplier

    def print_orders(self):
        print("\nТекущая сетка ордеров:")
        for order in self.orders:
            if not order.executed:
                print(
                    f"{order.order_type.upper()} | Цена: {order.price:.4f} | Объем: {order.volume:.4f} | ID: {order.id}"
                )

    def initialize_grid(self):
        if not self.initial_grid_created and self.current_price and self.current_ema:
            print(f"Initializing grid at price {self.current_price}, EMA: {self.current_ema}")

            lower_bound = self.current_price * (1 - self.grid_step_percent * self.max_orders / 100)
            upper_bound = self.current_price * (1 + self.grid_step_percent * self.max_orders / 100)

            self.current_grid_bounds = (lower_bound, upper_bound)
            self._build_virtual_grid()  # создаем виртуальные уровни

            buy_prices, sell_prices = self.create_asymmetric_grid(
                self.current_ema,
                self.current_price,
                lower_bound,
                upper_bound,
                self.grid_step_percent,
                self.grid_step_percent,
            )

            buy_prices = buy_prices[: self.max_orders]
            sell_prices = sell_prices[: self.max_orders]

            if not buy_prices or not sell_prices:
                print("Error: Failed to generate grid prices!")
                return

            base_volume = self.calculate_base_volume(self.current_price)

            for i, price in enumerate((buy_prices)):
                volume = base_volume * (self.volume_growth_factor**i)
                if price < self.current_ema:
                    self.place_order("buy", price, volume)

            for i, price in enumerate((sell_prices)):
                volume = base_volume * (self.volume_growth_factor**i)
                if price > self.current_ema:
                    self.place_order("sell", price, volume)

            # Хедж на стартовой сетке
            if len(self.price_history) > 30:
                price_returns = np.diff(np.log(self.price_history[-30:]))
                volatility = np.std(price_returns) * np.sqrt(252)
            else:
                volatility = 0.5

            estimated_volume = self.estimate_grid_volume()
            hedge_position = self.options_manager.create_hedge_strategy(
                self.current_price, (lower_bound, upper_bound), volatility, estimated_volume
            )

            self.free_margin -= hedge_position["total_cost"]
            self.hedge_active = True

            # ВАЖНО!
            self.check_and_refill_orders()
            self.update_display()
            # Печатаем сетку после создания
            self.print_orders()
            self.initial_grid_created = True

    def should_update_grid(self, executed_order):
        # Определение, нужно ли обновлять сетку на основе условий исполнения ордера
        # Например, можно проверить, достиг ли рынок определенных критериев или настроек
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
        Расчет свободной маржи
        Free Margin = Balance + Floating Profit - Used Margin
        """
        # Маржа под открытые позиции (по цене входа)
        margin_used = sum(pos.volume * pos.entry_price for pos in self.positions)

        # Маржа под неисполненные ордера
        orders_margin = sum(
            order.volume * order.price * (1 + MAKER_COMMISSION_RATE) for order in self.orders if not order.executed
        )

        # Обновляем свободную маржу
        previous_margin = self.free_margin
        self.free_margin = self.balance + self.floating_profit - margin_used - orders_margin

        # print(f"\nFree margin calculation:")
        # print(f"Balance: {self.balance:.8f}")
        # print(f"Floating profit: {self.floating_profit:.8f}")
        # print(f"Used margin (positions): {margin_used:.8f}")
        # print(f"Used margin (orders): {orders_margin:.8f}")
        # print(f"Previous free margin: {previous_margin:.8f}")
        # print(f"Current free margin: {self.free_margin:.8f}")

    def calculate_free_margin(self):
        total_position_value = sum(pos.volume * self.current_price for pos in self.positions)
        self.free_margin = self.balance - total_position_value

    def get_order_history(self):
        return self.order_history

    def get_open_positions(self):
        return self.positions

    def get_closed_positions(self):
        return self.closed_positions

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

    def calculate_floating_profit(self, current_price):
        """
        Расчет плавающей прибыли по всем открытым позициям
        """
        # Сохраняем текущую цену для других расчетов
        self.current_price = current_price

        # Считаем плавающую прибыль по всем открытым позициям
        self.floating_profit = sum(pos.update_floating_profit(current_price) for pos in self.positions)

        # print(f"\nFloating profit calculation at price {current_price:.8f}:")
        # print(f"Number of open positions: {len(self.positions)}")
        # print(f"Total floating profit: {self.floating_profit:.8f}")

        return self.floating_profit

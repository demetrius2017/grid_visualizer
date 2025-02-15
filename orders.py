import uuid
import numpy as np
from scipy import stats
from options_manager import OptionsManager


class Position:
    def __init__(self, order_type, price, volume, commission_rate=0.00016):
        self.order_type = order_type
        self.entry_price = price
        self.volume = volume
        self.floating_profit = 0
        self.closed = False
        self.exit_price = None
        self.profit = 0
        self.commission = price * volume * commission_rate

    def update_floating_profit(self, current_price):
        if self.order_type == "buy":
            self.floating_profit = (current_price - self.entry_price) * self.volume
        else:  # sell
            self.floating_profit = (self.entry_price - current_price) * self.volume
        return self.floating_profit

    def close_position(self, exit_price):
        self.exit_price = exit_price
        if self.order_type == "buy":
            self.profit = (
                exit_price - self.entry_price
            ) * self.volume - self.commission
        else:  # sell
            self.profit = (
                self.entry_price - exit_price
            ) * self.volume - self.commission
        self.closed = True
        return self.profit


class Order:
    def __init__(self, order_type, price, volume, commission_rate):
        self.id = str(uuid.uuid4())[:8]
        self.order_type = order_type
        self.price = price
        self.volume = volume
        self.executed = False
        self.execution_price = None
        self.profit = 0
        self.commission_rate = commission_rate
        self.commission = 0  # Будет рассчитано при исполнении ордера


class OrderManager:
    def __init__(
        self,
        initial_balance,
        commission_rate,
        grid_size,
        graph,
        grid_step_percent=0.2,
        min_grid_coverage=0.20,
        min_orders=20,
        max_orders=50,
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission_rate = commission_rate
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
        self.price_history = []  # Хранение истории цен
        self.graph = graph
        self.positions = []
        self.closed_positions = []
        self.executed_orders_history = []
        self.price_distribution = []
        self.distribution_period = 1000  # Количество последних цен для анализа
        self.num_bins = 50  # Количество столбиков в гистограмме
        self.volume_growth_factor = 1.2  # Коэффициент роста объема ордеров
        self.price_frequency = {}
        # Новые атрибуты для динамического шага сетки
        self.consecutive_buys = 0
        self.consecutive_sells = 0
        self.base_grid_step = grid_step_percent
        self.max_grid_step_multiplier = 8  # Максимальное увеличение шага сетки
        self.total_profit = 0
        self.total_commission = 0
        # Существующая инициализация...
        self.options_manager = OptionsManager(commission_rate)
        self.hedge_active = False
        self.hedge_update_frequency = 24 * 60  # Обновление хеджа раз в сутки
        self.hedge_counter = 0

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
        hist, bin_edges = np.histogram(
            self.price_distribution, bins=self.num_bins, density=True
        )

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

        base_volume = volume
        distribution_coeff = self.calculate_distribution_coefficient()
        frequency_coeff = self.calculate_price_frequency_coefficient(price)

        if order_type == "buy":
            volume = base_volume * distribution_coeff * frequency_coeff
        else:  # sell
            volume = base_volume * (2 - distribution_coeff) * frequency_coeff
        required_margin = price * volume
        estimated_commission = price * volume * self.commission_rate
        if price > 0 and self.free_margin >= required_margin + estimated_commission:
            order = Order(order_type, price, volume, self.commission_rate)
            self.orders.append(order)
            self.free_margin -= required_margin + estimated_commission
            # print(
            #     f"Placed {order_type} order at {price} for {volume} units. Estimated commission: {estimated_commission:.8f}"
            # )
        else:
            print(
                f"Insufficient margin to place {order_type} order at {price} for {volume} units."
            )

    def create_asymmetric_grid(
        self,
        ema,
        current_price,
        lower_bound,
        upper_bound,
        buy_step,
        sell_step,
        num_levels=10,
    ):
        """
        Создание асимметричной сетки ордеров
        """
        # Защита от некорректных значений
        if lower_bound >= current_price or current_price >= upper_bound:
            current_price = (lower_bound + upper_bound) / 2

        # Рассчитываем количество уровней для покупки и продажи
        price_range = upper_bound - lower_bound
        buy_range = current_price - lower_bound
        sell_range = upper_bound - current_price

        # Определяем пропорциональное количество уровней
        buy_levels = max(1, int(num_levels * (buy_range / price_range)))
        sell_levels = max(1, int(num_levels * (sell_range / price_range)))

        # Создаем массивы цен с динамическим шагом
        buy_prices = []
        for i in range(buy_levels):
            price = current_price * (1 - (i + 1) * buy_step / 100)
            if price >= lower_bound:
                buy_prices.append(price)

        sell_prices = []
        for i in range(sell_levels):
            price = current_price * (1 + (i + 1) * sell_step / 100)
            if price <= upper_bound:
                sell_prices.append(price)

        return buy_prices, sell_prices

    def update_hedge_position(self, current_price):
        """
        Обновление хеджирующей позиции
        """
        if not self.hedge_active:
            # Создаем новую хеджирующую позицию
            lower_bound = current_price * (
                1 - self.grid_step_percent / 100 * self.max_orders
            )
            upper_bound = current_price * (
                1 + self.grid_step_percent / 100 * self.max_orders
            )

            # Рассчитываем волатильность на основе исторических данных
            if len(self.price_history) > 30:
                price_returns = np.diff(np.log(self.price_history[-30:]))
                volatility = np.std(price_returns) * np.sqrt(
                    252
                )  # Годовая волатильность
            else:
                volatility = 0.5  # Значение по умолчанию

            hedge_position = self.options_manager.create_hedge_strategy(
                current_price, (lower_bound, upper_bound), volatility
            )

            # Вычитаем стоимость хеджа из свободной маржи
            self.free_margin -= hedge_position["total_cost"]
            self.hedge_active = True

    def update_existing_orders(self, ema, current_price):
        for order in self.orders:
            if not order.executed:
                if order.order_type == "buy" and order.price > current_price:
                    new_price = min(
                        order.price, ema * (1 - self.grid_step_percent / 100)
                    )
                    order.price = new_price
                    # print(f"Updated buy order {order.id} price to {new_price}")
                elif order.order_type == "sell" and order.price < current_price:
                    new_price = max(
                        order.price, ema * (1 + self.grid_step_percent / 100)
                    )
                    order.price = new_price
                    # print(f"Updated sell order {order.id} price to {new_price}")

    def calculate_base_volume(self, current_price):
        return (
            self.free_margin * 0.01 / current_price
        )  # Используем 1% свободной маржи для базового объема

    def calculate_order_volume(self, current_price):
        # Рассчитываем общий объем для всей сетки
        total_volume = (
            self.free_margin * 0.5 / current_price
        )  # Используем 50% свободной маржи для всей сетки

        # Делим общий объем на количество уровней сетки
        volume_per_level = total_volume / (
            self.grid_size * 2
        )  # Умножаем на 2, так как у нас buy и sell ордера

        return volume_per_level

    def check_orders(self, current_price):
        self.current_price = current_price
        self.calculate_floating_profit(current_price)
        self.calculate_free_margin()
        self.update_price_distribution(current_price)

        # Проверяем хедж до проверки ордеров
        if self.hedge_active:
            hedge_payout, triggered = self.options_manager.calculate_hedge_payout(
                current_price
            )
            if triggered:
                # Если сработал хедж:
                print(f"Hedge triggered at price {current_price}")
                # 1. Получаем выплату
                self.balance += hedge_payout
                self.free_margin += hedge_payout

                # 2. Закрываем все открытые позиции по текущей цене
                for position in self.positions[:]:
                    profit = position.close_position(current_price)
                    self.profit += profit
                    self.closed_positions.append(position)
                self.positions = []

                # 3. Отменяем все активные ордера
                self.orders = [order for order in self.orders if order.executed]

                # 4. Деактивируем хедж
                self.hedge_active = False
                return  # Прекращаем обработку ордеров до возврата цены в диапазон

        # Проверяем, нужно ли создать новую сетку
        if not self.hedge_active and self.current_ema is not None:
            lower_bound, upper_bound = self.calculate_grid_boundaries(
                self.current_ema, self.price_history
            )
            # Если цена вернулась в диапазон после срабатывания хеджа
            if (
                lower_bound < current_price < upper_bound
                and self.options_manager.last_trigger_price is not None
            ):
                print(f"Creating new grid after hedge trigger at price {current_price}")
                # Создаем новую сетку и новый хедж
                self.options_manager.last_trigger_price = None
                self.update_grid(self.current_ema, current_price, self.price_history)
                self.hedge_active = True

        # Обычная обработка ордеров
        last_price = (
            self.price_history[-2]
            if len(self.price_history) > 1
            else self.current_price
        )
        price_range = sorted([last_price, current_price])

        orders_executed = False
        for order in self.orders[:]:
            if not order.executed:
                if (
                    order.order_type == "buy"
                    and price_range[0] <= order.price <= price_range[1]
                ) or (
                    order.order_type == "sell"
                    and price_range[0] <= order.price <= price_range[1]
                ):
                    self.execute_order(order, order.price)
                    orders_executed = True

        # Проверяем необходимость создания новой сетки
        active_orders = [order for order in self.orders if not order.executed]
        if len(active_orders) == 0 and not self.options_manager.last_trigger_price:
            print(
                f"Creating new grid after all orders executed at price {current_price}"
            )
            self.update_grid(self.current_ema, current_price, self.price_history)
            self.hedge_active = True

        if orders_executed:
            self.update_display()

    def execute_order(self, order, execution_price):
        order.executed = True
        order.execution_price = execution_price
        order.commission = order.volume * execution_price * self.commission_rate
        order.execution_time = len(self.price_history) - 1

        opposite_position = next(
            (pos for pos in self.positions if pos.order_type != order.order_type), None
        )

        if opposite_position:
            profit = opposite_position.close_position(execution_price)
            self.profit += profit
            self.closed_positions.append(opposite_position)
            self.positions.remove(opposite_position)
        else:
            new_position = Position(
                order.order_type, execution_price, order.volume, self.commission_rate
            )
            self.positions.append(new_position)
            self.total_commission += order.commission

        self.update_balance()

        if order.order_type == "buy":
            self.consecutive_buys += 1
            self.consecutive_sells = 0
        else:  # sell
            self.consecutive_sells += 1
            self.consecutive_buys = 0

        self.calculate_free_margin()

        self.executed_orders_history.append(order)
        if len(self.executed_orders_history) > self.distribution_period * 2:
            self.executed_orders_history.pop(0)

        self.update_price_distribution(execution_price)
        self.orders.remove(order)
        if order not in self.order_history:
            self.order_history.append(order)

    def update_grid(self, ema, current_price, price_history):
        """
        Создание новой сетки и хеджа
        """
        print(f"Updating grid at price {current_price}")
        lower_bound, upper_bound = self.calculate_grid_boundaries(ema, price_history)

        # Рассчитываем динамические шаги сетки для покупок и продаж
        buy_step = self.calculate_dynamic_grid_step("buy")
        sell_step = self.calculate_dynamic_grid_step("sell")

        # Генерируем цены для покупки и продажи
        buy_prices, sell_prices = self.create_asymmetric_grid(
            ema, current_price, lower_bound, upper_bound, buy_step, sell_step
        )

        base_volume = self.calculate_base_volume(current_price)

        # Размещаем новые ордера
        for i, price in enumerate(buy_prices):
            volume = base_volume * (self.volume_growth_factor**i)
            self.place_order("buy", price, volume)

        for i, price in enumerate(sell_prices):
            volume = base_volume * (self.volume_growth_factor**i)
            self.place_order("sell", price, volume)

        # Создаем новый хедж
        if len(price_history) > 30:
            price_returns = np.diff(np.log(price_history[-30:]))
            volatility = np.std(price_returns) * np.sqrt(252)
        else:
            volatility = 0.5

        self.options_manager.create_hedge_strategy(
            current_price, (lower_bound, upper_bound), volatility
        )

        # Обновляем график
        if hasattr(self.graph, "set_full_data"):
            buy_orders = [
                order
                for order in self.orders
                if order.order_type == "buy" and not order.executed
            ]
            sell_orders = [
                order
                for order in self.orders
                if order.order_type == "sell" and not order.executed
            ]
            distribution_data = self.get_price_distribution_data()

            self.graph.set_full_data(
                price_history,
                [ema] * len(price_history),
                buy_orders,
                sell_orders,
                self.order_history,
                distribution_data,
            )

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

    def initialize_grid(self):
        if self.current_ema is not None and len(self.price_history) > 0:
            # print("Initializing grid.")
            self.update_grid(self.current_ema, self.current_price, self.price_history)
        else:
            print("Grid initialization skipped due to missing data.")

    def should_update_grid(self, executed_order):
        # Определение, нужно ли обновлять сетку на основе условий исполнения ордера
        # Например, можно проверить, достиг ли рынок определенных критериев или настроек
        return True  # По умолчанию всегда обновлять после исполнения

    def calculate_total_commission(self):
        total_commission = sum(order.commission for order in self.executed_orders)
        total_commission += sum(
            order.volume * order.price * order.commission_rate
            for order in self.orders
            if not order.executed
        )
        return total_commission

    def update_balance(self):
        self.balance = self.initial_balance + self.total_profit - self.total_commission

    def calculate_floating_profit(self, current_price):
        self.floating_profit = sum(
            pos.update_floating_profit(current_price) for pos in self.positions
        )

    def calculate_free_margin(self):
        total_position_value = sum(
            pos.volume * self.current_price for pos in self.positions
        )
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
        self.total_commission = sum(
            position.commission for position in self.closed_positions
        )
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

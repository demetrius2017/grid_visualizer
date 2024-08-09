import uuid
import numpy as np


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
    def __init__(self, initial_balance, commission_rate, grid_size, grid_step_percent=1.0):
        self.balance = initial_balance
        self.commission_rate = commission_rate
        self.grid_size = grid_size
        self.grid_step_percent = grid_step_percent
        self.orders = []
        self.executed_orders = []
        self.order_history = []
        self.profit = 0
        self.floating_profit = 0
        self.free_margin = initial_balance
        self.current_ema = None  # Хранение текущего значения EMA
        self.current_price = None  # Хранение текущей цены
        self.price_history = []  # Хранение истории цен

    def calculate_grid_boundaries(self, ema, price_history, coverage_percent=0.15):
        hist_min = np.min(price_history)
        hist_max = np.max(price_history)
        range_size = hist_max - hist_min
        lower_bound = max(ema - range_size * coverage_percent, hist_min)
        upper_bound = min(ema + range_size * coverage_percent, hist_max)
        
        # Убедимся, что границы находятся на некотором расстоянии от текущей цены
        current_price = price_history[-1]
        min_distance = range_size * 0.05  # Минимальное расстояние - 5% от диапазона цен
        
        if current_price - lower_bound < min_distance:
            lower_bound = current_price - min_distance
        
        if upper_bound - current_price < min_distance:
            upper_bound = current_price + min_distance
        
        return lower_bound, upper_bound

    def place_order(self, order_type, price, volume):
        required_margin = price * volume
        estimated_commission = price * volume * self.commission_rate
        if price > 0 and self.free_margin >= required_margin + estimated_commission:
            order = Order(order_type, price, volume, self.commission_rate)
            self.orders.append(order)
            self.free_margin -= required_margin + estimated_commission
            print(
                f"Placed {order_type} order at {price} for {volume} units. Estimated commission: {estimated_commission:.8f}"
            )
        else:
            print(f"Insufficient margin to place {order_type} order at {price} for {volume} units.")

    def create_asymmetric_grid(self, ema, current_price, lower_bound, upper_bound, num_levels=10):
        buy_range = ema - lower_bound
        sell_range = upper_bound - ema

        if buy_range > sell_range:
            buy_levels = int(num_levels * (buy_range / (buy_range + sell_range)))
            sell_levels = num_levels - buy_levels
        else:
            sell_levels = int(num_levels * (sell_range / (buy_range + sell_range)))
            buy_levels = num_levels - sell_levels

        buy_prices = np.linspace(lower_bound, min(ema, current_price), buy_levels + 1)[:-1]
        sell_prices = np.linspace(max(ema, current_price), upper_bound, sell_levels + 1)[1:]

        return buy_prices, sell_prices

    def place_order(self, order_type, price, volume):
        print(f"Attempting to place order: Type={order_type}, Price={price}, Volume={volume}")
        required_margin = price * volume
        estimated_commission = price * volume * self.commission_rate
        print(
            f"Required margin: {required_margin}, Estimated commission: {estimated_commission}, Free margin: {self.free_margin}"
        )

        if price > 0 and self.free_margin >= required_margin + estimated_commission:
            order = Order(order_type, price, volume, self.commission_rate)
            self.orders.append(order)
            self.free_margin -= required_margin + estimated_commission
            print(
                f"Placed {order_type} order at {price} for {volume} units. Estimated commission: {estimated_commission:.8f}"
            )
            return True
        else:
            print(f"Insufficient margin to place {order_type} order at {price} for {volume} units.")
            return False

    def update_grid(self, ema, current_price, price_history):
        print(f"Updating grid with EMA={ema}, Current Price={current_price}")
        lower_bound, upper_bound = self.calculate_grid_boundaries(ema, price_history)

        # Рассчитываем шаг сетки
        grid_step = (upper_bound - lower_bound) / (self.grid_size * 2)

        # Генерируем цены для покупки и продажи
        all_prices = np.linspace(lower_bound, upper_bound, self.grid_size * 2)

        # Разделяем цены на buy и sell в зависимости от текущей цены
        buy_prices = [price for price in all_prices if price < current_price]
        sell_prices = [price for price in all_prices if price > current_price]

        # Проверяем, есть ли у нас достаточно уровней для buy и sell
        if len(buy_prices) < self.grid_size / 2:
            additional_buy_levels = self.grid_size // 2 - len(buy_prices)
            for i in range(additional_buy_levels):
                new_price = max(lower_bound, current_price - (i + 1) * grid_step)
                buy_prices.append(new_price)

        if len(sell_prices) < self.grid_size / 2:
            additional_sell_levels = self.grid_size // 2 - len(sell_prices)
            for i in range(additional_sell_levels):
                new_price = min(upper_bound, current_price + (i + 1) * grid_step)
                sell_prices.append(new_price)

        # Сортируем цены
        buy_prices.sort(reverse=True)
        sell_prices.sort()

        print(f"Calculated buy prices: {buy_prices}")
        print(f"Calculated sell prices: {sell_prices}")

        # Удалим существующие неисполненные ордера
        self.orders = [order for order in self.orders if order.executed]

        volume = self.calculate_order_volume(current_price)

        total_margin_required = sum([price * volume for price in buy_prices + sell_prices])
        if total_margin_required > self.free_margin:
            print(f"Warning: Not enough free margin to place all orders. Adjusting volume.")
            volume *= self.free_margin / total_margin_required

        self.place_grid_orders(buy_prices, sell_prices, volume)
        print(f"Orders placed. Total Orders: {len(self.orders)}")

        def update_existing_orders(self, ema, current_price):
            for order in self.orders:
                if not order.executed:
                    if order.order_type == "buy" and order.price > current_price:
                        new_price = min(order.price, ema * (1 - self.grid_step_percent / 100))
                        order.price = new_price
                        print(f"Updated buy order {order.id} price to {new_price}")
                    elif order.order_type == "sell" and order.price < current_price:
                        new_price = max(order.price, ema * (1 + self.grid_step_percent / 100))
                        order.price = new_price
                        print(f"Updated sell order {order.id} price to {new_price}")

    def calculate_order_volume(self, current_price):
        # Рассчитываем общий объем для всей сетки
        total_volume = self.free_margin * 0.5 / current_price  # Используем 50% свободной маржи для всей сетки

        # Делим общий объем на количество уровней сетки
        volume_per_level = total_volume / (self.grid_size * 2)  # Умножаем на 2, так как у нас buy и sell ордера

        return volume_per_level

    def check_orders(self, current_price):
        self.current_price = current_price
        self.calculate_floating_profit(current_price)
        self.calculate_free_margin()
        print(f"Checking orders at current price: {current_price}")
        for order in self.orders[:]:  # Используем копию списка, чтобы избежать проблем при удалении элементов
            if not order.executed:
                if (order.order_type == "buy" and current_price <= order.price) or (
                    order.order_type == "sell" and current_price >= order.price
                ):
                    print(f"Executing order: {order.id}")
                    self.execute_order(order, current_price)
                elif (order.order_type == "buy" and current_price > order.price) or (
                    order.order_type == "sell" and current_price < order.price
                ):
                    print(f"Removing invalid order: {order.id}")
                    self.orders.remove(order)

        # После проверки всех ордеров, обновляем сетку
        if self.current_ema is not None:
            self.update_grid(self.current_ema, current_price, self.price_history)

    def execute_order(self, order, execution_price):
        print(f"Executing order {order.id} at price {execution_price}")
        order.executed = True
        order.execution_price = execution_price
        order.commission = order.volume * execution_price * order.commission_rate

        if order.order_type == "buy":
            self.balance -= order.volume * execution_price + order.commission
            new_price = order.price * (1 + self.grid_step_percent / 100)
            self.place_order("sell", new_price, order.volume)
        elif order.order_type == "sell":
            self.balance += order.volume * execution_price - order.commission
            new_price = order.price * (1 - self.grid_step_percent / 100)
            self.place_order("buy", new_price, order.volume)

        order.profit = (
            order.volume
            * (execution_price - order.price if order.order_type == "sell" else order.price - execution_price)
        ) - order.commission
        self.profit += order.profit

        self.executed_orders.append(order)
        self.orders.remove(order)
        if order not in self.order_history:
            self.order_history.append(order)

        self.update_free_margin_after_execution()
        print(
            f"Executed {order.order_type} order at {execution_price} for {order.volume} units. Commission: {order.commission:.8f}, Profit: {order.profit:.8f}, New balance: {self.balance:.8f}, Total Profit: {self.profit:.8f}, Free Margin: {self.free_margin:.8f}"
        )

        if self.current_ema is not None and self.current_price is not None and self.price_history:
            print("Updating grid after order execution.")
            self.update_grid(self.current_ema, self.current_price, self.price_history)

    def initialize_grid(self):
        if self.current_ema is not None and len(self.price_history) > 0:
            print("Initializing grid.")
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
            order.volume * order.price * order.commission_rate for order in self.orders if not order.executed
        )
        return total_commission

    def calculate_floating_profit(self, current_price):
        self.floating_profit = self.calculate_unrealized_pnl(current_price)
        for order in self.orders:
            if not order.executed:
                if order.order_type == "buy":
                    self.floating_profit += (current_price - order.price) * order.volume
                elif order.order_type == "sell":
                    self.floating_profit += (order.price - current_price) * order.volume
        self.floating_profit -= self.calculate_total_commission()
        print(f"Floating Profit calculated: {self.floating_profit}")

    def calculate_unrealized_pnl(self, current_price):
        unrealized_pnl = 0
        for order in self.orders:
            if order.executed:
                if order.order_type == "buy":
                    unrealized_pnl += order.volume * (current_price - order.execution_price)
                else:
                    unrealized_pnl += order.volume * (order.execution_price - current_price)
        return unrealized_pnl

    def calculate_free_margin(self):
        total_order_value = sum(order.price * order.volume for order in self.orders if not order.executed)
        self.free_margin = self.balance + self.floating_profit - total_order_value
        print(f"Total Order Value: {total_order_value}, Free Margin: {self.free_margin}")

    def update_free_margin_after_execution(self):
        total_executed_order_value = sum(order.price * order.volume for order in self.orders if order.executed)
        self.free_margin = self.balance + self.floating_profit - total_executed_order_value
        print(f"Updated Free Margin: {self.free_margin}")

    def get_order_history(self):
        return self.order_history

    def get_balance(self):
        return self.balance

    def get_profit(self):
        return self.profit

    def get_floating_profit(self):
        return self.floating_profit

    def get_free_margin(self):
        return self.free_margin

    def initialize_grid(self):
        if self.current_ema is not None and len(self.price_history) > 0:
            print("Initializing grid.")
            self.update_grid(self.current_ema, self.current_price, self.price_history)
        else:
            print("Grid initialization skipped due to missing data.")

    def clear_orders(self):
        self.orders = []
        self.executed_orders = []
        self.order_history = []
        self.floating_profit = 0
        print("Cleared all orders")

    def place_grid_orders(self, buy_prices, sell_prices, volume):
        for price in buy_prices:
            if not self.place_order("buy", price, volume):
                break
        for price in sell_prices:
            if not self.place_order("sell", price, volume):
                break

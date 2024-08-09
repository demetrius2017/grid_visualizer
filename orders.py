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
        else:
            print(f"Insufficient margin to place {order_type} order at {price} for {volume} units.")

    def update_grid(self, ema, current_price, price_history):
        print(f"Updating grid with EMA={ema}, Current Price={current_price}")

        if len(self.orders) == 0:
            lower_bound, upper_bound = self.calculate_grid_boundaries(ema, price_history)
            buy_prices, sell_prices = self.create_asymmetric_grid(ema, current_price, lower_bound, upper_bound)
            print(f"Calculated buy prices: {buy_prices}, sell prices: {sell_prices}")

            volume = self.calculate_order_volume(current_price)
            self.place_grid_orders(buy_prices, sell_prices, volume)
            print(f"New grid created. Total Orders: {len(self.orders)}")
        else:
            print("Grid update skipped. There are existing open orders.")

        self.update_existing_orders(ema, current_price)

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
        # Расчет объема ордера на основе свободной маржи и текущей цены
        return self.free_margin * 0.1 / current_price  # Используем 10% свободной маржи для каждого ордера

    def check_orders(self, current_price):
        self.current_price = current_price
        self.calculate_floating_profit(current_price)
        self.calculate_free_margin()
        print(f"Checking orders at current price: {current_price}")
        for order in self.orders:
            print(f"Order ID: {order.id}, Type: {order.order_type}, Price: {order.price}, Executed: {order.executed}")
            if not order.executed:
                if (order.order_type == "buy" and current_price <= order.price) or (
                    order.order_type == "sell" and current_price >= order.price
                ):
                    print(f"Executing order: {order.id}")
                    self.execute_order(order, current_price)

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
        """
        Размещает ордера по рассчитанным уровням цен для покупки и продажи.
        :param buy_prices: Список цен для покупки.
        :param sell_prices: Список цен для продажи.
        :param volume: Объем ордеров.
        """
        for price in buy_prices:
            self.place_order("buy", price, volume)

        for price in sell_prices:
            self.place_order("sell", price, volume)

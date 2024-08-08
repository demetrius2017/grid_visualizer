import time

class Order:
    def __init__(self, order_type, price, volume):
        self.order_type = order_type
        self.price = price
        self.volume = volume
        self.executed = False

class OrderManager:
    def __init__(self, grid_step_percent):
        self.orders = []
        self.balance = 10000
        self.order_history = []
        self.grid_step_percent = grid_step_percent
        self.profit = 0
        self.floating_profit = 0
        self.free_margin = self.balance

    def place_order(self, order_type, price, volume):
        required_margin = price * volume
        if price > 0 and self.free_margin >= required_margin:
            order = Order(order_type, price, volume)
            self.orders.append(order)
            self.free_margin -= required_margin
            print(f"Placed {order_type} order at {price} for {volume} units. Required Margin: {required_margin}, Free Margin: {self.free_margin}")
        else:
            print(f"Insufficient margin to place {order_type} order at {price} for {volume} units. Required Margin: {required_margin}, Free Margin: {self.free_margin}")

    def check_orders(self, current_price):
        self.calculate_floating_profit(current_price)
        self.calculate_free_margin()
        for order in self.orders:
            if not order.executed:
                if (order.order_type == 'buy' and current_price <= order.price) or (order.order_type == 'sell' and current_price >= order.price):
                    self.execute_order(order, current_price)

    def execute_order(self, order, execution_price):
        order.executed = True
        self.order_history.append(order)
        if order.order_type == 'buy':
            self.balance -= order.volume * execution_price
            new_price = order.price + (order.price * self.grid_step_percent / 100)
            self.place_order('sell', new_price, order.volume)
        elif order.order_type == 'sell':
            self.balance += order.volume * execution_price
            new_price = order.price - (order.price * self.grid_step_percent / 100)
            self.place_order('buy', new_price, order.volume)
        
        self.profit += order.volume * (execution_price - order.price if order.order_type == 'sell' else order.price - execution_price)
        self.update_free_margin_after_execution()
        print(f"Executed {order.order_type} order at {execution_price} for {order.volume} units. New balance: {self.balance}, Profit: {self.profit}, Free Margin: {self.free_margin}")

    def calculate_floating_profit(self, current_price):
        self.floating_profit = 0
        for order in self.orders:
            if not order.executed:
                if order.order_type == 'buy':
                    self.floating_profit += (current_price - order.price) * order.volume
                elif order.order_type == 'sell':
                    self.floating_profit += (order.price - current_price) * order.volume
        print(f"Floating Profit: {self.floating_profit}")

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

    def initialize_grid(self, ema, num_orders, volume):
        self.clear_orders()
        total_margin_to_use = self.balance * 0.50  # Используем 50% маржи
        volume_per_order = total_margin_to_use / (2 * num_orders)  # Делим на количество ордеров в обе стороны
        print(f"Total Margin to Use: {total_margin_to_use}, Volume per Order: {volume_per_order}")
        current_price = ema[-1]
        for i in range(num_orders):
            buy_price = current_price - (current_price * self.grid_step_percent / 100) * (i + 1)
            sell_price = current_price + (current_price * self.grid_step_percent / 100) * (i + 1)
            if buy_price < current_price:
                self.place_order('buy', buy_price, volume_per_order)
            if sell_price > current_price:
                self.place_order('sell', sell_price, volume_per_order)
        self.calculate_free_margin()
        print("Initial grid setup complete. Pausing for verification...")
        # time.sleep(5)  # Пауза на 5 секунд для проверки

    def clear_orders(self):
        # Add floating profit to the balance before clearing
        self.balance += self.floating_profit
        self.orders = []
        self.floating_profit = 0
        print("Cleared all existing orders")

    def update_grid(self, ema, num_orders, volume):
        self.clear_orders()
        self.initialize_grid(ema, num_orders, volume)

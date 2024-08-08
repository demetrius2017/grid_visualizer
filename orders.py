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

    def place_order(self, order_type, price, volume):
        if price > 0:
            order = Order(order_type, price, volume)
            self.orders.append(order)
            print(f"Placed {order_type} order at {price} for {volume} units")

    def check_orders(self, current_price):
        self.calculate_floating_profit(current_price)
        for order in self.orders:
            if not order.executed:
                if (order.order_type == "buy" and current_price <= order.price) or (
                    order.order_type == "sell" and current_price >= order.price
                ):
                    self.execute_order(order, current_price)

    def execute_order(self, order, execution_price):
        order.executed = True
        self.order_history.append(order)
        if order.order_type == "buy":
            self.balance -= order.volume * execution_price
            new_price = order.price + (order.price * self.grid_step_percent / 100)
            self.place_order("sell", new_price, order.volume)
        elif order.order_type == "sell":
            self.balance += order.volume * execution_price
            new_price = order.price - (order.price * self.grid_step_percent / 100)
            self.place_order("buy", new_price, order.volume)

        self.profit += order.volume * (
            execution_price - order.price if order.order_type == "sell" else order.price - execution_price
        )
        print(
            f"Executed {order.order_type} order at {execution_price} for {order.volume} units. New balance: {self.balance}, Profit: {self.profit}"
        )

    def calculate_floating_profit(self, current_price):
        self.floating_profit = 0
        for order in self.orders:
            if not order.executed:
                if order.order_type == "buy":
                    self.floating_profit += (current_price - order.price) * order.volume
                elif order.order_type == "sell":
                    self.floating_profit += (order.price - current_price) * order.volume
        print(f"Floating Profit: {self.floating_profit}")

    def get_order_history(self):
        return self.order_history

    def get_balance(self):
        return self.balance

    def get_profit(self):
        return self.profit

    def get_floating_profit(self):
        return self.floating_profit

    def initialize_grid(self, ema, num_orders, volume):
        self.clear_orders()
        for i in range(num_orders):
            buy_price = ema[-1] - (ema[-1] * self.grid_step_percent / 100) * (i + 1)
            sell_price = ema[-1] + (ema[-1] * self.grid_step_percent / 100) * (i + 1)
            self.place_order("buy", buy_price, volume)
            self.place_order("sell", sell_price, volume)

    def clear_orders(self):
        self.orders = []
        print("Cleared all existing orders")

    def update_grid(self, ema, num_orders, volume):
        self.clear_orders()
        self.initialize_grid(ema, num_orders, volume)

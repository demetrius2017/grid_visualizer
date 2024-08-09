import uuid

class Order:
    def __init__(self, order_type, price, volume):
        self.id = str(uuid.uuid4())[:8]  # Генерируем уникальный ID
        self.order_type = order_type
        self.price = price
        self.volume = volume
        self.executed = False
        self.execution_price = None
        self.profit = 0  # Добавляем атрибут для хранения прибыли
        self.commission = 0  # Добавляем атрибут для хранения комиссии


class OrderManager:
    def __init__(self, grid_step_percent):
        self.orders = []  # Инициализируем пустой список для хранения ордеров
        self.executed_orders = []  # Список для хранения исполненных ордеров
        self.balance = 10000
        self.order_history = []
        self.grid_step_percent = grid_step_percent
        self.profit = 0
        self.floating_profit = 0
        self.free_margin = self.balance
        self.commission_rate = 0.0067  # 0.67% комиссия, можно изменить по необходимости

    def place_order(self, order_type, price, volume):
        required_margin = price * volume
        commission = price * volume * self.commission_rate
        if price > 0 and self.free_margin >= required_margin + commission:
            order = Order(order_type, price, volume)
            self.orders.append(order)  # Добавляем ордер в список
            self.free_margin -= required_margin + commission
            print(f"Placed {order_type} order at {price} for {volume} units.")
        else:
            print(f"Insufficient margin to place {order_type} order at {price} for {volume} units.")

    def check_orders(self, current_price):
        self.calculate_floating_profit(current_price)
        self.calculate_free_margin()
        for order in self.orders:
            if not order.executed:
                if (order.order_type == "buy" and current_price <= order.price) or (
                    order.order_type == "sell" and current_price >= order.price
                ):
                    self.execute_order(order, current_price)

    def execute_order(self, order, execution_price):
        order.executed = True
        order.execution_price = execution_price
        self.executed_orders.append(order)
        self.orders.remove(order)  # Удаляем исполненный ордер из списка активных ордеровактивных ордеров
        commission = order.volume * execution_price * self.commission_rate

        if order.order_type == "buy":
            self.balance -= order.volume * execution_price + commission
            new_price = order.price * (1 + self.grid_step_percent / 100)
            self.place_order("sell", new_price, order.volume)
        elif order.order_type == "sell":
            self.balance += order.volume * execution_price - commission
            new_price = order.price * (1 - self.grid_step_percent / 100)
            self.place_order("buy", new_price, order.volume)

        order.profit = (
            order.volume
            * (execution_price - order.price if order.order_type == "sell" else order.price - execution_price)
            - commission
        )
        self.profit += order.profit
        self.order_history.append(order)
        self.update_free_margin_after_execution()
        print(
            f"Executed {order.order_type} order at {execution_price} for {order.volume} units. Commission: {commission}, New balance: {self.balance}, Profit: {self.profit}, Free Margin: {self.free_margin}"
        )
    def calculate_total_commission(self):
        total_commission = 0
        for order in self.orders:
            if order.executed:
                total_commission += order.volume * order.execution_price * self.commission_rate
            else:
                total_commission += order.volume * order.price * self.commission_rate
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

    def initialize_grid(self, ema, num_orders, volume):
        self.clear_orders()
        current_price = ema[-1]
        for i in range(num_orders):
            buy_price = current_price * (1 - self.grid_step_percent / 100 * (i + 1))
            sell_price = current_price * (1 + self.grid_step_percent / 100 * (i + 1))
            if buy_price > 0:
                self.place_order('buy', buy_price, volume)
            if sell_price > 0:
                self.place_order('sell', sell_price, volume)
        self.calculate_free_margin()

    def update_grid(self, ema, num_orders, volume):
        for order in self.orders:
            if not order.executed:
                if order.order_type == "buy":
                    new_price = ema[-1] - (ema[-1] * self.grid_step_percent / 100) * (
                        num_orders - len([o for o in self.orders if o.order_type == "buy" and o.executed])
                    )
                    if new_price > 0:  # Проверка, чтобы цена ордера не была отрицательной
                        order.price = new_price
                elif order.order_type == "sell":
                    new_price = ema[-1] + (ema[-1] * self.grid_step_percent / 100) * (
                        num_orders - len([o for o in self.orders if o.order_type == "sell" and o.executed])
                    )
                    if new_price > 0:
                        order.price = new_price

    def clear_orders(self):
        self.orders = []
        self.executed_orders = []
        self.floating_profit = 0
        print("Cleared all orders")

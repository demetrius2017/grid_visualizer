class Order:
    def __init__(self, order_type, price, volume):
        self.order_type = order_type
        self.price = price
        self.volume = volume
        self.executed = False

class OrderManager:
    def __init__(self):
        self.orders = []
        self.balance = 10000
        self.order_history = []

    def place_order(self, order_type, price, volume):
        order = Order(order_type, price, volume)
        self.orders.append(order)

    def check_orders(self, current_price):
        for order in self.orders:
            if not order.executed:
                if (order.order_type == 'buy' and current_price <= order.price) or (order.order_type == 'sell' and current_price >= order.price):
                    self.execute_order(order, current_price)

    def execute_order(self, order, execution_price):
        order.executed = True
        self.order_history.append(order)
        if order.order_type == 'buy':
            self.balance -= order.volume * execution_price
        elif order.order_type == 'sell':
            self.balance += order.volume * execution_price

    def get_order_history(self):
        return self.order_history

    def get_balance(self):
        return self.balance

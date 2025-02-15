class OptionsManager:
    def __init__(self, commission_rate=0.0004):  # 0.04% как на Binance
        self.commission_rate = commission_rate
        self.active_options = []
        self.options_history = []
        self.total_premium_paid = 0
        self.total_premium_received = 0
        self.last_trigger_price = None  # Цена, при которой сработал последний опцион

    def calculate_option_price(self, S, K, sigma):
        """
        Упрощенный расчет цены опциона для барьерных уровней
        S: текущая цена
        K: цена страйка
        sigma: волатильность
        """
        # Используем упрощенную формулу, где премия зависит от расстояния до барьера и волатильности
        distance_to_strike = abs(S - K) / S
        premium = S * distance_to_strike * sigma * 0.5
        return premium

    def create_hedge_strategy(self, current_price, grid_bounds, volatility):
        """
        Создание стратегии хеджирования для сетки
        """
        lower_bound, upper_bound = grid_bounds

        # Расчет премий
        put_price = self.calculate_option_price(current_price, lower_bound, volatility)
        call_price = self.calculate_option_price(current_price, upper_bound, volatility)

        # Создание опционной позиции
        hedge_position = {
            "put": {"strike": lower_bound, "premium": put_price, "triggered": False},
            "call": {"strike": upper_bound, "premium": call_price, "triggered": False},
            "total_cost": (put_price + call_price) * (1 + self.commission_rate),
            "start_price": current_price,
        }

        self.active_options = [
            hedge_position
        ]  # Всегда держим только одну активную стратегию
        self.total_premium_paid += hedge_position["total_cost"]
        self.last_trigger_price = None

        return hedge_position

    def calculate_hedge_payout(self, current_price):
        """
        Расчет выплаты по хеджирующей позиции
        """
        if not self.active_options:
            return 0, False

        position = self.active_options[0]
        total_payout = 0
        triggered = False

        if self.last_trigger_price is not None:
            return 0, False

        # Проверяем границы
        if (
            current_price < position["put"]["strike"]
            and not position["put"]["triggered"]
        ):
            payout = position["put"]["strike"] - current_price
            total_payout += payout
            position["put"]["triggered"] = True
            triggered = True
            self.last_trigger_price = current_price

        elif (
            current_price > position["call"]["strike"]
            and not position["call"]["triggered"]
        ):
            payout = current_price - position["call"]["strike"]
            total_payout += payout
            position["call"]["triggered"] = True
            triggered = True
            self.last_trigger_price = current_price

        if triggered:
            position["trigger_price"] = current_price  # Сохраняем цену триггера
            self.total_premium_received += total_payout
            self.options_history.append(position)
            self.active_options = []

        return total_payout, triggered

    def get_hedge_metrics(self):
        """
        Получение метрик хеджирования
        """
        return {
            "active_positions": len(self.active_options),
            "total_premium_paid": self.total_premium_paid,
            "total_premium_received": self.total_premium_received,
            "net_premium": self.total_premium_received - self.total_premium_paid,
        }

    def get_current_hedge_exposure(self, current_price):
        """
        Расчет текущего риска по хеджирующим позициям
        """
        if not self.active_options:
            return 0

        position = self.active_options[0]
        # Считаем потенциальную выплату
        put_exposure = max(0, position["put"]["strike"] - current_price)
        call_exposure = max(0, current_price - position["call"]["strike"])
        return put_exposure + call_exposure

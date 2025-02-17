class OptionsManager:
    def __init__(self):
        self.positions = []
        self.last_trigger_price = None
        self.options_history = []  # История срабатывания опционов

    def create_hedge_strategy(self, current_price, grid_bounds, volatility, position_volume=1.0):
        """
        Создает стратегию хеджирования с учетом объема позиции

        Args:
            current_price (float): Текущая цена
            grid_bounds (tuple): Границы сетки (нижняя, верхняя)
            volatility (float): Волатильность
            position_volume (float): Объем позиции для хеджирования
        """
        lower_bound, upper_bound = grid_bounds

        # Создаем put опцион на нижней границе
        put_option = {
            "type": "put",
            "strike": lower_bound,
            "premium": self._calculate_premium(current_price, lower_bound, volatility),
            "triggered": False,
            "volume": position_volume,
        }

        # Создаем call опцион на верхней границе
        call_option = {
            "type": "call",
            "strike": upper_bound,
            "premium": self._calculate_premium(current_price, upper_bound, volatility),
            "triggered": False,
            "volume": position_volume,
        }

        # Сохраняем позицию
        position = {
            "put": put_option,
            "call": call_option,
            "total_cost": (put_option["premium"] + call_option["premium"]) * position_volume,
            "create_price": current_price,
        }

        self.positions = [position]
        return position

    def calculate_hedge_payout(self, current_price, position_volume=1.0):
        """
        Расчет выплаты по хеджу без ограничения на положительные значения
        """
        if not self.positions:
            return 0, None

        position = self.positions[0]
        payout = 0
        trigger_type = None

        # Расчет выплаты при выходе за нижнюю границу
        if current_price < position["put"]["strike"]:
            payout = (position["put"]["strike"] - current_price) * position_volume
            trigger_type = "put"
            print(
                f"Put option triggered: strike={position['put']['strike']:.8f}, "
                f"current_price={current_price:.8f}, payout={payout:.8f}"
            )

        # Расчет выплаты при выходе за верхнюю границу
        elif current_price > position["call"]["strike"]:
            payout = (current_price - position["call"]["strike"]) * position_volume
            trigger_type = "call"
            print(
                f"Call option triggered: strike={position['call']['strike']:.8f}, "
                f"current_price={current_price:.8f}, payout={payout:.8f}"
            )

        if trigger_type:
            self.options_history.append(
                {
                    "type": trigger_type,
                    "strike": position[trigger_type]["strike"],
                    "trigger_price": current_price,
                    "payout": payout,
                    "volume": position_volume,
                    "trigger_time": len(self.options_history),
                    "premium": position[trigger_type]["premium"],
                }
            )
            self.last_trigger_price = current_price

        return payout, trigger_type

    def _calculate_premium(self, current_price, strike_price, volatility):
        """Простой расчет премии опциона"""
        distance = abs(current_price - strike_price) / current_price
        time_factor = 1  # Можно добавить учет времени до экспирации
        return current_price * distance * volatility * time_factor * 0.1  # 10% от теоретической стоимости

    def get_hedge_metrics(self):
        """Возвращает метрики хеджирования"""
        if not self.positions:
            return {"cost": 0, "coverage": 0, "put_strike": None, "call_strike": None}

        position = self.positions[0]
        return {
            "cost": position["total_cost"],
            "coverage": (position["call"]["strike"] - position["put"]["strike"]) / position["create_price"],
            "put_strike": position["put"]["strike"],
            "call_strike": position["call"]["strike"],
        }

    @property
    def active_options(self):
        """Возвращает информацию об активных опционах"""
        if not self.positions:
            return []

        position = self.positions[0]
        active_opts = []

        # Добавляем put опцион, если он не сработал
        if not position["put"]["triggered"]:
            active_opts.append(
                {
                    "type": "put",
                    "strike": position["put"]["strike"],
                    "premium": position["put"]["premium"],
                    "volume": position["put"]["volume"],
                }
            )

        # Добавляем call опцион, если он не сработал
        if not position["call"]["triggered"]:
            active_opts.append(
                {
                    "type": "call",
                    "strike": position["call"]["strike"],
                    "premium": position["call"]["premium"],
                    "volume": position["call"]["volume"],
                }
            )

        return active_opts

    def get_current_hedge_exposure(self, current_price):
        """Возвращает текущую экспозицию хеджа"""
        if not self.positions:
            return 0

        position = self.positions[0]

        # Для put опциона
        put_exposure = max(0, position["put"]["strike"] - current_price) * position["put"]["volume"]
        # Для call опциона
        call_exposure = max(0, current_price - position["call"]["strike"]) * position["call"]["volume"]

        return put_exposure + call_exposure

    def get_current_strikes(self):
        """Возвращает текущие границы хеджирования"""
        if not self.positions:
            return {"put": {"strike": None, "premium": 0}, "call": {"strike": None, "premium": 0}}

        position = self.positions[0]
        return {
            "put": {"strike": position["put"]["strike"], "premium": position["put"]["premium"]},
            "call": {"strike": position["call"]["strike"], "premium": position["call"]["premium"]},
        }

from datetime import datetime, timedelta
import requests


class Converter:
    LINK = r"https://free.currencyconverterapi.com/api/v6/convert?q={frm}_{to}&compact=y"

    def __init__(self, base_amount, from_="USD", to="RUB", update_period=180):
        self.base_amount = base_amount
        self.last_update = datetime.utcnow() - timedelta(days=365)
        self._from = from_
        self._to = to
        self.current = base_amount
        self.period = update_period

    def force_update(self):
        self.current = requests.get(
            self.LINK.format(frm=self._from, to=self._to)
        ).json()[self._from + "_" + self._to]["val"]

    def update(self):
        if datetime.utcnow() - self.last_update > timedelta(minutes=self.period):
            try:
                self.force_update()
            except Exception:
                fallback_period = self.period // 3
                if fallback_period < 1:
                    fallback_period = 1
                self.last_update = datetime.utcnow() - timedelta(minutes=fallback_period)

    def convert(self, amount=1.0):
        self.update()
        return amount * self.current


usd_rub_converter = Converter(65)

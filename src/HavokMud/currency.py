import logging
import math
import re

from HavokMud.data_loader import load_data_file

logger = logging.getLogger(__name__)

exchange_data = {}
base_values = {}
base_type = None
sorted_coins = []
reverse_sorted_coins = []
coin_names = []


def load_exchange_data():
    global exchange_data
    exchange_data = load_data_file("exchange.json")

    global base_values
    base_values = {coin_type: item.get("basevalue", 0) for (coin_type, item) in exchange_data.items()}
    base_value = min(base_values.values())

    global base_type
    base_types = [coin_type for (coin_type, value) in base_values.items() if value == base_value]
    base_type = base_types[0]

    global sorted_coins
    sorted_coins = sorted(base_values.items(), key=lambda x: x[1], reverse=True)

    global reverse_sorted_coins
    reverse_sorted_coins = list(reversed(sorted_coins))

    global coin_names
    coin_names = [name.upper() for name in base_values.keys()]


class Currency(object):
    coinRe = re.compile(r'^(?P<quantity>\d+)\s*(?P<type>[a-z]+)$', re.I)

    def __init__(self, currency=None, coins=None, value=None):
        if not base_values:
            load_exchange_data()

        self.holdings = {}
        if isinstance(currency, Currency):
            self.holdings.update(currency.holdings)

        if isinstance(coins, str):
            coins = coins.split()
        elif not coins:
            coins = []

        for coin in coins:
            coin_value = self.parse_coin(coin)
            self.holdings.update({coin_type: value + self.holdings.get(coin_type, 0)
                                  for (coin_type, value) in coin_value.items()})

        if value:
            self.holdings.update({base_type: value + self.holdings.get(base_type, 0)})

    @staticmethod
    def parse_coin(coin):
        match = Currency.coinRe.match(coin)
        if not match:
            logger.error("Coin '%s' does not parse" % coin)
            return {}

        coin_type = match.group("type")
        coin_item = exchange_data.get(coin_type, None)
        if not coin_item:
            logger.error("Coin '%s' has an unconfigured type" % coin)
            return {}

        count = match.group("quantity")
        if not count:
            count = 0
        else:
            count = int(count)

        if not count:
            return {}

        return {coin_type: count}

    def convert_to_base(self, store=False):
        values = [quantity * base_values.get(coin_type, 0)
                  for (coin_type, quantity) in self.holdings.items()]
        value = sum(values)
        if store:
            self.holdings = {base_type: value}
        return value

    def convert_to_minimal(self):
        total_value = self.convert_to_base()
        holdings = {}
        for (coin_type, value) in sorted_coins:
            (count, total_value) = divmod(total_value, value)
            if count:
                holdings[coin_type] = count

        self.holdings = holdings

    def add_value(self, currency):
        for (coin_type, count) in currency.holdings.items():
            if count:
                self.add_coins(coin_type, count)

    def add_tokens(self, tokens):
        parts = tokens.split()
        if len(parts) != 2:
            return
        self.add_coins(parts[1].lower(), int(parts[0]))

    def add_coins(self, coin_type, count):
        if count:
            self.holdings.update({coin_type: count + self.holdings.get(coin_type, 0)})

    def remove_coins(self, coin_type, count):
        if count:
            new_count = self.holdings.get(coin_type, 0) - count
            if new_count < 0:
                raise ValueError("Can't remove more coins than exist")
            if new_count == 0:
                self.holdings.pop(coin_type, 0)
            else:
                self.holdings.update({coin_type: new_count})

    def subtract_value(self, currency):
        our_value = self.convert_to_base()
        their_value = currency.convert_to_base()
        if our_value < their_value:
            raise ValueError("That would be negative money")
        if our_value == their_value:
            self.holdings.clear()
            return

        # Subtract the amounts, coin by coin
        self.holdings.update({coin_type: self.holdings.get(coin_type, 0) - count
                              for (coin_type, count) in currency.holdings.items()
                              if count})

        # Now to break coins so we have no negatives, starting at smallest coin
        remainder = 0
        for (index, (coin_type, basevalue)) in enumerate(reverse_sorted_coins):
            count = self.holdings.get(coin_type, 0)
            if count >= 0:
                continue

            bigger_coin = reverse_sorted_coins[index + 1]
            bigger_coin_value = bigger_coin[1] / basevalue
            bigger_coin_type = bigger_coin[0]

            need_count = -count
            bigger_coin_count = int(math.ceil(need_count / bigger_coin_value))
            added_count = int(bigger_coin_count * bigger_coin_value)
            count += added_count

            self.holdings.update({
                coin_type: count,
                bigger_coin_type: self.holdings.get(bigger_coin_type, 0) - bigger_coin_count,
            })

            # In case the next coin up is not an integer multiple of this coin, we would
            # have some change.  Just make that be all base coins, and we'll add it as
            # minimal change in the end
            my_remainder = (bigger_coin_count * bigger_coin[1]) - (added_count * basevalue)
            remainder += my_remainder

        # Convert any remainder to minimal change
        if remainder:
            remainder = Currency(value=remainder)
            remainder.convert_to_minimal()
            self.add_value(remainder)

    def minimal_payment(self, coins):
        payment_value = Currency(coins=coins).convert_to_base()
        value = self.convert_to_base()

        if payment_value > value:
            raise ValueError("That payment is more than the holdings")
        if payment_value == value:
            # Use it all!
            return Currency(currency=self)

        value = 0
        payment = Currency()
        for (coin_type, basevalue) in reverse_sorted_coins:
            delta_value = payment_value - value
            count = self.holdings.get(coin_type, 0)
            if not count:
                continue

            to_add = min(int(math.ceil(delta_value / basevalue)), count)
            if not to_add:
                continue

            payment.add_coins(coin_type, to_add)
            value += to_add * basevalue
            if value >= payment_value:
                break

        delta_value = value - payment_value
        if not delta_value:
            # Wow, exact change
            return payment

        # Now remove as much excess as possible
        for (coin_type, basevalue) in sorted_coins:
            if delta_value < basevalue:
                continue

            count = payment.holdings.get(coin_type, 0)
            if not count:
                continue

            to_remove = min(int(delta_value / basevalue), count)
            if not to_remove:
                continue

            payment.remove_coins(coin_type, to_remove)
            value -= to_remove * basevalue
            delta_value = value - payment_value

        return payment

    def __str__(self):
        holdings = ["%d%s" % (self.holdings.get(coin_type, 0), coin_type)
                    for (coin_type, value) in sorted_coins
                    if self.holdings.get(coin_type, 0)]
        if not holdings:
            return "0%s" % base_type
        return " ".join(holdings)

#! /usr/bin/env python3

from HavokMud.currency import Currency

currency = Currency(coins="3pp 6gp 2cp")
print(currency)
currency2 = Currency(currency=currency, coins="10ep")
print(currency2)
currency2.convert_to_base(store=True)
print(currency2)
currency2.convert_to_minimal()
print(currency2)
currency3 = Currency(value=12345)
print(currency3)
currency3.convert_to_minimal()
print(currency3)


print("BLAH")
currency = Currency(coins="1pp")
currency2 = Currency(coins="1cp")
currency.subtract_value(currency2)
print(currency)
currency.add_value(currency2)
print(currency)
currency.subtract_value(currency)
print(currency)
try:
    currency.subtract_value(currency2)
    print(currency)
except ValueError as e:
    print("Failed as expected: %s" % e)

currency = Currency(coins="1pp 6gp 3sp 4ep 5cp")
print(currency)
payment = currency.minimal_payment("3gp 5sp")
print(payment)

currency = Currency(coins="1pp 4gp 3sp 1ep 5cp")
print(currency)
payment = currency.minimal_payment("3gp 5sp")
print(payment)

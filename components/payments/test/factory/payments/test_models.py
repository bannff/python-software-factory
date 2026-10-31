import unittest
from decimal import Decimal
from factory.payments.runtime.models import Money, Currency


class TestMoney(unittest.TestCase):
    def test_addition(self):
        m1 = Money(amount=Decimal("10.50"), currency=Currency.USD)
        m2 = Money(amount=Decimal("5.25"), currency=Currency.USD)
        result = m1 + m2
        self.assertEqual(result.amount, Decimal("15.75"))
        self.assertEqual(result.currency, Currency.USD)

    def test_invalid_currency_addition(self):
        m1 = Money(amount=Decimal("10"), currency=Currency.USD)
        m2 = Money(amount=Decimal("10"), currency=Currency.EUR)
        with self.assertRaises(ValueError):
            _ = m1 + m2


if __name__ == "__main__":
    unittest.main()

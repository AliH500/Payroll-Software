from decimal import Decimal

import pytest

from domain.money import Money


def test_repr_does_not_leak_amount():
    m = Money(Decimal("1234.56"), "PKR")
    assert "1234" not in repr(m)
    assert "REDACTED" in repr(m)


def test_str_does_not_leak_amount():
    m = Money(Decimal("1234.56"), "PKR")
    assert "1234" not in str(m)
    assert "REDACTED" in str(m)


def test_f_string_does_not_leak_amount():
    m = Money(Decimal("1234.56"), "PKR")
    assert "1234" not in f"{m}"
    assert "1234" not in f"{m!s}"
    assert "1234" not in f"{m!r}"


def test_addition():
    assert (Money(Decimal("10"), "PKR") + Money(Decimal("5"), "PKR")).amount == Decimal("15")


def test_subtraction():
    assert (Money(Decimal("10"), "PKR") - Money(Decimal("5"), "PKR")).amount == Decimal("5")


def test_multiplication_int():
    assert (Money(Decimal("10"), "PKR") * 2).amount == Decimal("20")


def test_multiplication_reflected():
    assert (3 * Money(Decimal("10"), "PKR")).amount == Decimal("30")


def test_negation():
    assert (-Money(Decimal("10"), "PKR")).amount == Decimal("-10")


def test_currency_mismatch_addition_raises():
    a = Money(Decimal("1"), "PKR")
    b = Money(Decimal("1"), "ETB")
    with pytest.raises(ValueError, match="Cannot combine"):
        a + b


def test_unsupported_currency_raises():
    with pytest.raises(ValueError, match="Unsupported currency"):
        Money(Decimal("1"), "USD")


def test_non_decimal_amount_raises():
    with pytest.raises(TypeError, match="must be a Decimal"):
        Money(1.0, "PKR")  # type: ignore[arg-type]


def test_money_is_immutable():
    m = Money(Decimal("1"), "PKR")
    with pytest.raises(AttributeError):
        m.amount = Decimal("2")  # type: ignore[misc]


def test_format_uses_currency_and_thousands_separator():
    assert Money(Decimal("12345.67"), "PKR").format() == "PKR 12,345.67"
    assert Money(Decimal("1000000"), "ETB").format() == "ETB 1,000,000.00"
    assert Money(Decimal("0"), "PKR").format() == "PKR 0.00"


def test_format_two_decimal_places_even_when_input_is_whole():
    assert Money(Decimal("85000"), "PKR").format() == "PKR 85,000.00"


def test_format_handles_negatives():
    assert Money(Decimal("-500"), "PKR").format() == "PKR -500.00"


def test_format_does_not_replace_str_redaction():
    m = Money(Decimal("999"), "PKR")
    # .format() shows the amount; __str__/__repr__ keep redacting (log safety).
    assert "999" in m.format()
    assert "999" not in str(m)
    assert "999" not in repr(m)

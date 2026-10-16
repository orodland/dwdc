import datetime as dt
from decimal import Decimal

import pytest

from brokerrecon.config import Formats
from brokerrecon.model import EXTRACTION_UNCERTAIN, MISSING_FIELD
from brokerrecon.normalize import NormError, dec_str, parse_contract_month, parse_number

AS_OF = dt.date(2026, 12, 31)


@pytest.mark.parametrize("raw,fmt,expected", [
    ("1,234.50", Formats(), "1234.5"),
    ("1.250.000,00", Formats(decimal_separator=",", thousands_separator="."), "1250000"),
    ("(42)", Formats(), "-42"),
    ("42-", Formats(), "-42"),
    ("0,08345", Formats(decimal_separator=",", thousands_separator="."), "0.08345"),
])
def test_parse_number_locales(raw, fmt, expected):
    assert dec_str(parse_number(raw, fmt)) == expected


@pytest.mark.parametrize("raw", ["1O0", "l5", "12,5", "1.2.3x"])
def test_homoglyphs_and_wrong_locale_are_uncertain_not_guessed(raw):
    with pytest.raises(NormError) as e:
        parse_number(raw, Formats())
    assert e.value.code == EXTRACTION_UNCERTAIN


def test_empty_is_missing():
    with pytest.raises(NormError) as e:
        parse_number("  ", Formats())
    assert e.value.code == MISSING_FIELD


def test_no_rounding_ever():
    assert dec_str(Decimal("442.2500")) == "442.25"
    assert dec_str(Decimal("100")) == "100"
    assert dec_str(Decimal("0.000")) == "0"


@pytest.mark.parametrize("raw,style,expected", [
    ("DEC27", "MONYY", "2027-12"),
    ("Mar-2028", "MON-YYYY", "2028-03"),
    ("2027-07", "YYYY-MM", "2027-07"),
    ("Z7", "CODE_Y1", "2027-12"),
    ("H5", "CODE_Y1", "2035-03"),  # window is [as_of.year, as_of.year + 9]
    ("F25", "CODE_Y2", "2025-01"),
])
def test_contract_months(raw, style, expected):
    assert parse_contract_month(raw, style, AS_OF)[0] == expected


def test_bad_contract_month_is_uncertain():
    with pytest.raises(NormError) as e:
        parse_contract_month("DCE27", "MONYY", AS_OF)
    assert e.value.code == EXTRACTION_UNCERTAIN


def test_price_conventions_eighths_and_units(config_dir):
    from brokerrecon.model import Cell, Step
    from brokerrecon.normalize import parse_price
    from brokerrecon.reference import load_reference

    ref = load_reference(config_dir)
    steps: list[Step] = []
    eighths = Formats(price_format={"ZC": "eighths_apostrophe"})
    assert parse_price("442'2", "ZC", Cell("442'2", {}), eighths, ref, steps, "price") == Decimal("442.25")
    with pytest.raises(NormError):
        parse_price("442'9", "ZC", Cell("442'9", {}), eighths, ref, steps, "price")
    dollars = Formats(price_unit={"ZC": "dollars"})
    assert parse_price("4.4225", "ZC", Cell("4.4225", {"type": "number"}), dollars, ref, steps, "price") == Decimal("442.25")
    assert [s.rule for s in steps] == ["fraction_eighths", "unit_dollars_to_cents"]

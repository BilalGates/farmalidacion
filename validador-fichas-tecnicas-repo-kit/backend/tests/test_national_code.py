import pytest

from pharma_validator_api.national_code import (
    NationalCodeError,
    national_code_search_term,
    parse_national_code,
)


def test_six_digits_remain_literal_and_have_no_supplied_control() -> None:
    code = parse_national_code("654789")

    assert code.canonical_six == "654789"
    assert code.source_literal == "654789"
    assert code.check_digit is None
    assert code.check_digit_status == "not_supplied"


def test_seventh_digit_is_preserved_but_not_claimed_as_valid() -> None:
    code = parse_national_code("6547892")

    assert code.canonical_six == "654789"
    assert code.source_literal == "6547892"
    assert code.check_digit == "2"
    assert code.check_digit_status == "not_validated"


def test_leading_zero_is_not_lost() -> None:
    assert parse_national_code("012345").canonical_six == "012345"


def test_form_whitespace_is_removed_without_changing_the_digits() -> None:
    code = parse_national_code(" 654789 \n")

    assert code.source_literal == "654789"


@pytest.mark.parametrize(
    "value",
    ["", "12345", "12345678", "654.789", "654 789", "ABC789", "６５４７８９"],
)
def test_other_formats_are_rejected_instead_of_normalized(value: str) -> None:
    with pytest.raises(
        NationalCodeError,
        match="debe contener seis o siete dígitos",
    ):
        parse_national_code(value)


def test_search_accepts_six_or_seven_but_uses_only_the_working_code() -> None:
    assert national_code_search_term("654789") == "654789"
    assert national_code_search_term("6547892") == "654789"


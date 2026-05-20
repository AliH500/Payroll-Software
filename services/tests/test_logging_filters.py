import logging

from services.observability.logging_filters import (
    REDACTED,
    SENSITIVE_KEYS,
    SensitiveDataFilter,
)


def make_record(msg="test", args=None, extra=None):
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    return record


def test_filter_returns_true_so_record_is_emitted():
    assert SensitiveDataFilter().filter(make_record()) is True


def test_dict_args_with_sensitive_key_are_masked():
    # LogRecord auto-unwraps a single-element tuple containing a dict.
    f = SensitiveDataFilter()
    record = make_record(msg="paying %(salary)s", args=({"salary": 5000},))
    f.filter(record)
    assert record.args["salary"] == REDACTED


def test_dict_args_with_non_sensitive_keys_pass_through():
    f = SensitiveDataFilter()
    record = make_record(msg="event for %(employee_id)s", args=({"employee_id": 42},))
    f.filter(record)
    assert record.args["employee_id"] == 42


def test_extra_kwargs_with_sensitive_key_are_masked():
    f = SensitiveDataFilter()
    record = make_record(extra={"net_pay": 1234})
    f.filter(record)
    assert record.net_pay == REDACTED


def test_extra_kwargs_with_non_sensitive_key_pass_through():
    f = SensitiveDataFilter()
    record = make_record(extra={"employee_id": 42, "company_id": 7})
    f.filter(record)
    assert record.employee_id == 42
    assert record.company_id == 7


def test_standard_logrecord_fields_are_untouched():
    f = SensitiveDataFilter()
    record = make_record()
    original_name = record.name
    original_msg = record.msg
    f.filter(record)
    assert record.name == original_name
    assert record.msg == original_msg


def test_sensitive_key_set_covers_salary_pii_and_secrets():
    # Sanity check against silent removals.
    expected = {"salary", "net_pay", "national_id", "bank_account", "password"}
    assert expected.issubset(SENSITIVE_KEYS)

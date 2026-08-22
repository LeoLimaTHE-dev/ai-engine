import ast
import inspect

import pytest

from ai_engine.providers import retry as retry_module
from ai_engine.providers.errors import (
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from ai_engine.providers.retry import retry_provider_call


def make_error(
    error_type=ProviderError,
    *,
    retryable=True,
    retry_after_seconds=None,
    message="Provider failure",
):
    return error_type(
        provider="test",
        message=message,
        retryable=retryable,
        retry_after_seconds=retry_after_seconds,
    )


def call_with_policy(operation, *, sleep=lambda delay: None, **overrides):
    options = {
        "max_retries": 2,
        "base_delay_seconds": 1,
        "max_delay_seconds": 10,
        "sleep": sleep,
    }
    options.update(overrides)
    return retry_provider_call(operation, **options)


def test_success_on_first_attempt_returns_the_exact_object_without_sleeping():
    expected = object()
    calls = []
    sleeps = []

    result = call_with_policy(
        lambda: calls.append("call") or expected,
        sleep=sleeps.append,
    )

    assert result is expected
    assert calls == ["call"]
    assert sleeps == []


@pytest.mark.parametrize(
    ("max_retries", "expected_calls", "expected_sleeps"),
    [
        (0, 1, []),
        (1, 2, [1.0]),
        (2, 3, [1.0, 2.0]),
    ],
)
def test_max_retries_counts_attempts_after_the_initial_call(
    max_retries,
    expected_calls,
    expected_sleeps,
):
    calls = []
    sleeps = []

    def fail():
        calls.append("call")
        raise make_error()

    with pytest.raises(ProviderError):
        call_with_policy(
            fail,
            max_retries=max_retries,
            sleep=sleeps.append,
        )

    assert len(calls) == expected_calls
    assert sleeps == expected_sleeps


@pytest.mark.parametrize(
    "error",
    [
        make_error(retryable=False),
        make_error(ProviderRateLimitError, retryable=False),
    ],
)
def test_non_retryable_provider_error_is_raised_immediately(error):
    calls = []
    sleeps = []

    def fail():
        calls.append("call")
        raise error

    with pytest.raises(type(error)) as captured:
        call_with_policy(fail, sleep=sleeps.append)

    assert captured.value is error
    assert calls == ["call"]
    assert sleeps == []


@pytest.mark.parametrize(
    "error_type",
    [ProviderTimeoutError, ProviderConnectionError, ProviderError],
)
def test_retryable_common_errors_are_retried(error_type):
    calls = []
    sleeps = []

    def operation():
        calls.append("call")
        if len(calls) == 1:
            raise make_error(error_type)
        return "success"

    assert call_with_policy(operation, sleep=sleeps.append) == "success"
    assert calls == ["call", "call"]
    assert sleeps == [1.0]


@pytest.mark.parametrize("error", [RuntimeError("failure"), ValueError("failure"), OSError("failure")])
def test_non_provider_errors_are_not_retried_or_converted(error):
    calls = []
    sleeps = []

    def fail():
        calls.append("call")
        raise error

    with pytest.raises(type(error)) as captured:
        call_with_policy(fail, sleep=sleeps.append)

    assert captured.value is error
    assert calls == ["call"]
    assert sleeps == []


@pytest.mark.parametrize("failures", [1, 2])
def test_operation_can_succeed_after_retryable_failures(failures):
    expected = object()
    calls = []

    def operation():
        calls.append("call")
        if len(calls) <= failures:
            raise make_error()
        return expected

    result = call_with_policy(operation, max_retries=failures)

    assert result is expected
    assert len(calls) == failures + 1


def test_exhaustion_raises_the_last_error_with_its_cause_intact():
    sdk_causes = [RuntimeError("sdk first"), RuntimeError("sdk last")]
    errors = [make_error(message="first"), make_error(message="last")]
    errors[0].__cause__ = sdk_causes[0]
    errors[1].__cause__ = sdk_causes[1]

    def operation():
        raise errors.pop(0)

    with pytest.raises(ProviderError) as captured:
        call_with_policy(operation, max_retries=1)

    assert captured.value.args == ("last",)
    assert captured.value.__cause__ is sdk_causes[1]


def test_exponential_backoff_is_capped_and_has_no_sleep_after_success():
    sleeps = []
    calls = []

    def operation():
        calls.append("call")
        if len(calls) <= 6:
            raise make_error()
        return "success"

    result = call_with_policy(
        operation,
        max_retries=6,
        base_delay_seconds=1,
        max_delay_seconds=10,
        sleep=sleeps.append,
    )

    assert result == "success"
    assert sleeps == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]


@pytest.mark.parametrize(
    ("retry_after", "max_delay", "expected_sleep"),
    [
        (3.5, 10, [3.5]),
        (120, 10, [10.0]),
        (None, 10, [1.0]),
        (0, 10, [1.0]),
        (-1, 10, [1.0]),
    ],
)
def test_retry_after_priority_validation_and_cap(
    retry_after,
    max_delay,
    expected_sleep,
):
    attempts = iter([make_error(retry_after_seconds=retry_after), "success"])
    sleeps = []

    def operation():
        result = next(attempts)
        if isinstance(result, ProviderError):
            raise result
        return result

    assert call_with_policy(
        operation,
        max_delay_seconds=max_delay,
        sleep=sleeps.append,
    ) == "success"
    assert sleeps == expected_sleep


@pytest.mark.parametrize(
    ("overrides", "error_type"),
    [
        ({"max_retries": -1}, ValueError),
        ({"max_retries": 1.5}, TypeError),
        ({"max_retries": True}, TypeError),
        ({"base_delay_seconds": -1}, ValueError),
        ({"base_delay_seconds": float("inf")}, ValueError),
        ({"base_delay_seconds": "1"}, TypeError),
        ({"max_delay_seconds": -1}, ValueError),
        ({"max_delay_seconds": float("nan")}, ValueError),
        ({"max_delay_seconds": False}, TypeError),
    ],
)
def test_invalid_parameters_are_rejected_before_operation(overrides, error_type):
    calls = []

    with pytest.raises(error_type):
        call_with_policy(lambda: calls.append("call"), **overrides)

    assert calls == []


def test_base_delay_greater_than_max_delay_is_capped_from_first_retry():
    attempts = iter([make_error(), make_error(), "success"])
    sleeps = []

    def operation():
        result = next(attempts)
        if isinstance(result, ProviderError):
            raise result
        return result

    assert call_with_policy(
        operation,
        base_delay_seconds=10,
        max_delay_seconds=3,
        sleep=sleeps.append,
    ) == "success"
    assert sleeps == [3.0, 3.0]


def test_zero_max_delay_skips_sleep_entirely():
    attempts = iter([make_error(), "success"])
    sleeps = []

    def operation():
        result = next(attempts)
        if isinstance(result, ProviderError):
            raise result
        return result

    assert call_with_policy(
        operation,
        max_delay_seconds=0,
        sleep=sleeps.append,
    ) == "success"
    assert sleeps == []


def test_retry_module_does_not_import_provider_sdks():
    tree = ast.parse(inspect.getsource(retry_module))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    assert not any(
        name == "openai"
        or name == "anthropic"
        or name.startswith("google.genai")
        for name in imported_modules
    )

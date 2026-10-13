import pytest

from scripts.check_schema import TEST_DATABASE, TestTargetError, approved_test_url, require_test_marker


def approved_settings():
    return {
        "RUN_POSTGRES_TESTS": "1",
        "POSTGRES_TEST_PROJECT": "supplier-invoice-verification-check-" + "a" * 32,
        "POSTGRES_DB": TEST_DATABASE, "POSTGRES_USER": TEST_DATABASE,
        "POSTGRES_HOST": "db", "POSTGRES_PORT": "5432",
        "POSTGRES_PASSWORD": "synthetic-only-test-password",
    }


def test_approved_target_preserves_explicit_settings():
    settings = approved_settings()
    url = approved_test_url(settings)
    assert url.database == TEST_DATABASE
    assert url.username == TEST_DATABASE
    assert url.password == settings["POSTGRES_PASSWORD"]


@pytest.mark.parametrize("key", list(approved_settings()))
def test_missing_settings_never_fall_back_to_development(key):
    settings = approved_settings()
    settings.pop(key)
    with pytest.raises(TestTargetError):
        approved_test_url(settings)


@pytest.mark.parametrize(("key", "value"), [
    ("RUN_POSTGRES_TESTS", "0"), ("RUN_POSTGRES_TESTS", "true"),
    ("POSTGRES_TEST_PROJECT", "supplier-invoice-verification"),
    ("POSTGRES_TEST_PROJECT", "supplier-invoice-verification-check-" + "a" * 32 + "-extra"),
    ("POSTGRES_DB", "supplier_invoice"), ("POSTGRES_USER", "supplier_invoice"),
    ("POSTGRES_HOST", "localhost"), ("POSTGRES_PORT", "5433"),
    ("POSTGRES_PASSWORD", " "),
])
def test_unapproved_settings_are_rejected_before_connecting(key, value):
    settings = approved_settings()
    settings[key] = value
    with pytest.raises(TestTargetError):
        approved_test_url(settings)


def test_ci_project_is_approved():
    settings = approved_settings()
    settings["POSTGRES_TEST_PROJECT"] = "supplier-invoice-verification-ci-12345-2"
    assert approved_test_url(settings).database == TEST_DATABASE


class StubConnection:
    def __init__(self, *, database=TEST_DATABASE, user=TEST_DATABASE, version=170000, marker=None):
        self.target = (database, user, version)
        self.marker = marker
        self.last_query = ""

    def execute(self, statement):
        self.last_query = str(statement)
        return self

    def one(self):
        return self.target

    def scalar_one(self):
        return self.marker


@pytest.mark.parametrize("options", [
    {"database": "supplier_invoice"}, {"user": "supplier_invoice"},
    {"version": 160000}, {"marker": None}, {"marker": "another project"},
])
def test_connected_target_and_marker_must_match(options):
    with pytest.raises(TestTargetError):
        require_test_marker(StubConnection(**options), approved_settings())

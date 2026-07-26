import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-local",
        action="store_true",
        default=False,
        help="run tests that need a local database connection",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-local"):
        return
    skip_local = pytest.mark.skip(reason="needs --run-local")
    for item in items:
        if "local" in item.keywords:
            item.add_marker(skip_local)

"""conftest.py for integration tests — register --ollama-live option."""


def pytest_addoption(parser):
    parser.addoption(
        "--ollama-live", action="store_true", default=False,
        help="Run integration tests with live Ollama L1+L2 inference",
    )

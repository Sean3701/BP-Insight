"""All tests use disposable storage, including legacy API tests."""
import os
import tempfile

_storage = tempfile.TemporaryDirectory(prefix='vc-tests-')
os.environ['VC_DATA_DIR'] = _storage.name


def pytest_sessionfinish(session, exitstatus):
    from backend.database import engine
    engine.dispose()
    _storage.cleanup()

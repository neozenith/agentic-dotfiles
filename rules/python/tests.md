---
paths:
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/tests/**/*.py"
---

# Python Testing Rules

## No Mocks, No Patches, No Exceptions

**NEVER use mocking in tests.** This is non-negotiable.

### Forbidden

```python
# ❌ ALL OF THESE ARE FORBIDDEN
from unittest.mock import Mock, MagicMock, patch, create_autospec
from unittest import mock
import mock  # pytest-mock
from pytest_mock import mocker

# Never do this:
@patch("module.function")
def test_something(mock_fn):
    ...

# Never do this:
with patch.object(obj, "method"):
    ...

# Never do this:
mock_obj = MagicMock()
```

### Why Mocks Are Forbidden

1. **Mocks test your assumptions, not your code** - A passing mock test only proves you correctly guessed the interface
2. **Mocks hide bugs** - When the real implementation changes, mock tests keep passing
3. **Mocks create maintenance burden** - Every mock is technical debt that must track the real implementation
4. **Mocks give false confidence** - High coverage with mocks is meaningless coverage

### What To Do Instead

**Test real code or don't test it:**

```python
# ✅ CORRECT - test real behavior with real dependencies
def test_cache_stores_data(tmp_path):
    cache = CacheManager(tmp_path / "test.db")
    cache.init_schema()
    cache.store("key", "value")
    assert cache.get("key") == "value"
```

**Use dependency injection for external services:**

```python
# ✅ CORRECT - inject dependencies, test with real implementations
def process_data(db: Database, api: ApiClient):
    ...

# In tests, use real test instances:
def test_process_data(tmp_path):
    db = SqliteDatabase(tmp_path / "test.db")
    api = TestApiServer()  # Real server, not a mock
    result = process_data(db, api)
```

**Skip tests for code that can't be tested without mocks:**

```python
# ✅ CORRECT - if you can't test it for real, don't pretend
@pytest.mark.skip(reason="Requires external claude CLI")
def test_reflect_command():
    ...

# Or simply don't write the test at all
```

**Use pytest fixtures for setup:**

```python
# ✅ CORRECT - real fixtures with real cleanup
@pytest.fixture
def populated_cache(tmp_path):
    cache = CacheManager(tmp_path / "cache.db")
    cache.init_schema()
    # Add real test data
    yield cache
    cache.close()
```

### Capturing Output

Use pytest's built-in `capsys` fixture instead of patching print:

```python
# ✅ CORRECT
def test_prints_message(capsys):
    my_function()
    captured = capsys.readouterr()
    assert "expected output" in captured.out

# ❌ FORBIDDEN
with patch("builtins.print"):
    my_function()
```

### Testing CLI Arguments

Use real `argparse.Namespace` objects:

```python
# ✅ CORRECT
from argparse import Namespace

def test_main_dispatch():
    args = Namespace(command="status", format="json", verbose=False)
    result = main(args)

# ❌ FORBIDDEN
args = MagicMock()
args.command = "status"
```

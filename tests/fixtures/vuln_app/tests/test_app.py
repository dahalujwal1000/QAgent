def test_should_pass():
    assert 1 + 1 == 2


def test_should_fail():
    assert add(1, 2) == 4  # intentionally failing


def add(a, b):
    return a + b
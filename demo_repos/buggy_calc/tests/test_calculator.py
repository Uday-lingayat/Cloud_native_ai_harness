from calculator import add, divide, multiply, subtract


def test_add() -> None:
    assert add(-2, 5) == 3


def test_subtract() -> None:
    assert subtract(4, 9) == -5


def test_multiply() -> None:
    assert multiply(-3, 4) == -12


def test_divide() -> None:
    assert divide(7, 2) == 3.5

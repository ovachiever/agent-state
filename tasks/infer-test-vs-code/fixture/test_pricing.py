from pricing import apply_discount


def test_quarter_off():
    assert apply_discount(200.0, 25) == 150.0


def test_no_discount():
    assert apply_discount(80.0, 0) == 80.0


def test_rounding():
    assert apply_discount(99.99, 10) == 89.99


if __name__ == "__main__":
    test_quarter_off()
    test_no_discount()
    test_rounding()
    print("ok")

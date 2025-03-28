import pytest

from bajo import Abs, Add, Div, DivU, LongMul, LongMulU, Max, Min, Mul, Neg, R, Rem, RemU, Sub

from .helpers import randps32, rands32, randu32, run, u32, u32_ok
from .vm import IntegerOverflowError, ZeroDivisionError


def truncdiv(a: int, b: int):
    quotient = a // b
    if quotient < 0:
        quotient = (a + (b - 1)) // b
    remainder = a - quotient * b
    return quotient, remainder


def test_smoke():
    b = run(
        [
            Add(R[0], 8, 4),
            Sub(R[1], 8, 4),
            Mul(R[2], 8, 4),
            Div(R[3], 8, 4),
            DivU(R[4], 8, 4),
            Rem(R[5], 8, 4),
            RemU(R[6], 8, 4),
            LongMul(R[7], R[8], 8, 4),
            LongMulU(R[9], R[10], 8, 4),
            Min(R[11], -10, 20),
            Max(R[12], -10, 20),
            Abs(R[13], -10),
            Min(R[15], -5, 5, -10, 10),
            Max(R[16], -5, 5, -10, 10),
            Neg(R[17], 5),
        ]
    )
    assert b.r[0] == 12
    assert b.r[1] == 4
    assert b.r[2] == 32
    assert b.r[3] == 2
    assert b.r[4] == 2
    assert b.r[5] == 0
    assert b.r[6] == 0
    assert b.r[7] == 32 and b.r[8] == 0
    assert b.r[9] == 32 and b.r[10] == 0
    assert b.r[11] == -10
    assert b.r[12] == 20
    assert b.r[13] == 10
    #
    assert b.r[15] == -10
    assert b.r[16] == 10
    assert b.r[17] == -5


def test_add():
    b = run(Add(R[0], 0, -10))
    assert b.r[0] == -10

    b = run(Add(R[0], -10, -10))
    assert b.r[0] == -20

    b = run([Add(R[0], -10, -10), Add(R[1], R[0], R[0])])
    assert b.r[1] == -40

    b = run(Add(R[0], 0x7FFFFFFF, 0x7FFFFFFF))
    assert b.ru[0] == 0xFFFFFFFE
    assert b.r[0] == -2

    b = run(Add(R[0], 0x7FFFFFFF, 1))
    assert b.ru[0] == 0x80000000
    assert b.r[0] == -0x80000000

    b = run(Add(R[0], 1, 0x7FFFFFFF))
    assert b.ru[0] == 0x80000000
    assert b.r[0] == -0x80000000

    with u32_ok():
        b = run(Add(R[0], 0x80000000, 0x80000000))
        assert b.ru[0] == 0

    with u32_ok():
        b = run(Add(R[0], 0xFFFFFFFF, 0xFFFFFFFF))
        assert b.ru[0] == 0xFFFFFFFE
        assert b.r[0] == -2

    b = run(Add(R[0], -10, 20))
    assert b.r[0] == 10


def test_sub():
    b = run(Sub(R[0], 0, -10))
    assert b.r[0] == 10

    b = run(Sub(R[0], -20, -10))
    assert b.r[0] == -10

    b = run([Sub(R[0], -10, -20), Sub(R[1], R[0], R[0])])
    assert b.r[1] == 0

    b = run(Sub(R[0], 0x7FFFFFFF, 0x7FFFFFFF))
    assert b.ru[0] == 0

    b = run(Sub(R[0], 0x7FFFFFFF, 1))
    assert b.ru[0] == 0x7FFFFFFE

    b = run(Sub(R[0], 1, 0x7FFFFFFF))
    assert b.r[0] == -0x7FFFFFFE

    with u32_ok():
        b = run(Sub(R[0], 0x80000000, 0xF8000000))
        assert b.ru[0] == 0x88000000

    with u32_ok():
        b = run(Sub(R[0], 0, 0xFFFFFFFF))
        assert b.r[0] == 1

    b = run(Sub(R[0], -0x7FFFFFFF, 0x7FFFFFFF))
    assert b.r[0] == 2


def test_math():
    # full signed
    for _i in range(1024):
        a = rands32()
        b = rands32()
        assert run(Add(R[0], a, b)).ru[0] == u32(a + b)
        assert run(Sub(R[0], a, b)).ru[0] == u32(a - b)
        assert run(Mul(R[0], a, b)).ru[0] == u32(a * b)
        # make the Python divs behave as in C (our interpreter is C-based)
        if b != 0:
            quotient, remainder = truncdiv(a, b)
            assert run(Div(R[0], a, b)).ru[0] == u32(quotient)
            assert run(Rem(R[0], a, b)).ru[0] == u32(remainder)
        assert run(Min(R[0], a, b)).r[0] == min(a, b)
        assert run(Max(R[0], a, b)).r[0] == max(a, b)
        assert run(Abs(R[0], a)).r[0] == abs(a)
        assert run(Neg(R[0], a)).r[0] == -a

    # signed ops in unsigned range
    for _i in range(1024):
        a = randps32()
        b = randps32()
        if b != 0:
            assert run(Div(R[0], a, b)).ru[0] == u32(a // b)
            assert run(DivU(R[0], a, b)).ru[0] == u32(a // b)
            assert run(Rem(R[0], a, b)).ru[0] == u32(a % b)
            assert run(RemU(R[0], a, b)).ru[0] == u32(a % b)

    # unsigned range
    with u32_ok():
        for _i in range(1024):
            a = randu32()
            b = randu32()
            assert run(Add(R[0], a, b)).ru[0] == u32(a + b)
            assert run(Sub(R[0], a, b)).ru[0] == u32(a - b)
            assert run(Mul(R[0], a, b)).ru[0] == u32(a * b)
            if b != 0:
                assert run(DivU(R[0], a, b)).ru[0] == u32(a // b)
                assert run(RemU(R[0], a, b)).ru[0] == u32(a % b)
            assert run(Neg(R[0], a)).ru[0] == u32(-a)


def test_long_mul():
    for _i in range(1024):
        a = rands32()
        b = rands32()
        res = run(LongMul(R[0], R[1], a, b))
        assert (res.r[1] << 32) | (res.ru[0]) == a * b

    for _i in range(1024):
        a = randps32()
        b = randps32()
        res = run(LongMul(R[0], R[1], a, b))
        assert (res.r[1] << 32) | (res.ru[0]) == a * b
        res = run(LongMulU(R[0], R[1], a, b))
        assert (res.r[1] << 32) | (res.ru[0]) == a * b

    with u32_ok():
        for _i in range(1024):
            a = randu32()
            b = randu32()
            res = run(LongMulU(R[0], R[1], a, b))
            assert (res.ru[1] << 32) | (res.ru[0]) == a * b


def test_divbyzero():
    with pytest.raises(ZeroDivisionError):
        run(Div(R[0], 1, 0)).r[0] = 0
    with pytest.raises(ZeroDivisionError):
        run(DivU(R[0], 1, 0)).r[0] = 0
    with pytest.raises(ZeroDivisionError):
        run(Rem(R[0], 1, 0)).r[0] = 0
    with pytest.raises(ZeroDivisionError):
        run(RemU(R[0], 1, 0)).r[0] = 0


def test_int_overflow():
    # special cases: most negative / -1
    with pytest.raises(IntegerOverflowError):
        assert run(Div(R[0], -0x80000000, -1)).ru[0] == 0x80000000
    # this one is actually ok
    assert run(Rem(R[0], -0x80000000, -1)).ru[0] == 0

    with u32_ok():
        assert run(DivU(R[0], 0x80000000, 1)).ru[0] == 0x80000000
        assert run(DivU(R[0], 0x80000000, 0xFFFFFFFF)).ru[0] == 0

    #  these should't rise
    assert run(Add(R[0], -0x80000000, -1)).ru[0] == 0x7FFFFFFF
    assert run(Sub(R[0], -0x80000000, -1)).ru[0] == 0x80000001
    assert run(Mul(R[0], -0x80000000, -1)).ru[0] == 0x80000000
    assert run(Add(R[0], -0x80000000, -0x80000000)).ru[0] == 0
    assert run(Sub(R[0], -0x80000000, -0x80000000)).ru[0] == 0
    assert run(Mul(R[0], -0x80000000, -0x80000000)).ru[0] == 0


def test_minmax_var():
    for _ in range(32):
        a = rands32()
        b = rands32()
        c = rands32()
        d = rands32()

        assert run(Min(R[0], a, b, c, d)).r[0] == min(a, b, c, d)
        assert run(Max(R[0], a, b, c, d)).r[0] == max(a, b, c, d)

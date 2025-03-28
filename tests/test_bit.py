from bajo import BitAnd, BitOr, BitXor, Inv, LShift, R, RShift, RShiftU

from .helpers import rands32, randu32, run, s32, u32, u32_ok


def test_common():
    for _i in range(64):
        a = rands32()
        b = rands32()
        assert run(BitAnd(R[0], a, b)).r[0] == a & b
        assert run(BitOr(R[0], a, b)).r[0] == a | b
        assert run(Inv(R[0], a)).r[0] == ~a
        assert run(BitXor(R[0], a, b)).r[0] == a ^ b

    with u32_ok():
        for _i in range(64):
            a = randu32()
            b = randu32()
            assert run(BitAnd(R[0], a, b)).ru[0] == u32(a & b)
            assert run(BitOr(R[0], a, b)).ru[0] == u32(a | b)
            assert run(Inv(R[0], a)).ru[0] == u32(~a)
            assert run(BitXor(R[0], a, b)).ru[0] == u32(a ^ b)

    for a in (0, 1, -1, 0x7FFFFFFF, -0x80000000):
        for b in (0, 1, -1, 0x7FFFFFFF, -0x80000000):
            assert run(BitAnd(R[0], a, b)).r[0] == a & b
            assert run(BitOr(R[0], a, b)).r[0] == a | b
            assert run(Inv(R[0], a)).r[0] == ~a
            assert run(BitXor(R[0], a, b)).r[0] == a ^ b

    with u32_ok():
        for a in (0, 0x7FFFFFFF, 0xFFFFFFFF):
            for b in (0, 0x7FFFFFFF, 0xFFFFFFFF):
                assert run(BitAnd(R[0], a, b)).ru[0] == u32(a & b)
                assert run(BitOr(R[0], a, b)).ru[0] == u32(a | b)
                assert run(Inv(R[0], a)).ru[0] == u32(~a)
                assert run(BitXor(R[0], a, b)).ru[0] == u32(a ^ b)


def test_shift():
    assert run(RShift(R[0], 0, 0)).r[0] == 0
    for _ in range(128):
        for s in range(34):
            a = rands32()
            assert run(LShift(R[0], a, s)).ru[0] == (a << s) & 0xFFFFFFFF
            assert run(RShift(R[0], a, s)).r[0] == a >> s

    with u32_ok():
        for _ in range(128):
            for s in range(34):
                a = randu32()
                assert run(LShift(R[0], a, s)).ru[0] == (a << s) & 0xFFFFFFFF
                assert run(RShift(R[0], a, s)).r[0] == s32(a) >> s
                assert run(RShiftU(R[0], a, s)).ru[0] == a >> s

    # shift amounts are unsigned and clamped to 32
    assert run(LShift(R[0], 10, -1)).ru[0] == 0
    assert run(RShift(R[0], 12, -1)).ru[0] == 0
    assert run(RShift(R[0], -12345, -1)).r[0] == -1
    assert run(RShiftU(R[0], 10, -1)).ru[0] == 0

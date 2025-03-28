from bajo import R, TstEq, TstGe, TstGeU, TstGt, TstGtU, TstLe, TstLeU, TstLt, TstLtU, TstNe

from .helpers import run, u32, u32_ok


def test_cond():
    for a in [0, 1, -1, -0x80000000, 0x7FFFFFFF]:
        for b in [0, 1, -1, -0x80000000, 0x7FFFFFFF]:
            assert run(TstEq(R[0], a, b)).r[0] == (a == b)
            assert run(TstNe(R[0], a, b)).r[0] == (a != b)
            assert run(TstLt(R[0], a, b)).r[0] == (a < b)
            assert run(TstLe(R[0], a, b)).r[0] == (a <= b)
            assert run(TstGt(R[0], a, b)).r[0] == (a > b)
            assert run(TstGe(R[0], a, b)).r[0] == (a >= b)
            assert run(TstLtU(R[0], a, b)).r[0] == (u32(a) < u32(b))
            assert run(TstLeU(R[0], a, b)).r[0] == (u32(a) <= u32(b))
            assert run(TstGtU(R[0], a, b)).r[0] == (u32(a) > u32(b))
            assert run(TstGeU(R[0], a, b)).r[0] == (u32(a) >= u32(b))

    with u32_ok():
        for a in [0, 1, 0x80000000, 0xFFFFFFFF]:
            for b in [0, 1, 0x80000000, 0xFFFFFFFF]:
                assert run(TstLtU(R[0], a, b)).r[0] == (a < b)
                assert run(TstLeU(R[0], a, b)).r[0] == (a <= b)
                assert run(TstGtU(R[0], a, b)).r[0] == (a > b)
                assert run(TstGeU(R[0], a, b)).r[0] == (a >= b)


def test_cond_sugar():
    for a in [0, 1, -1, -0x80000000, 0x7FFFFFFF]:
        for b in [0, 1, -1, -0x80000000, 0x7FFFFFFF]:
            assert run([R[1].set(a), R[2].set(b), R[0].set(R[1] == R[2])]).r[0] == (a == b)
            assert run([R[1].set(a), R[2].set(b), R[0].set(R[1] != R[2])]).r[0] == (a != b)
            assert run([R[1].set(a), R[2].set(b), R[0].set(R[1] < R[2])]).r[0] == (a < b)
            assert run([R[1].set(a), R[2].set(b), R[0].set(R[1] > R[2])]).r[0] == (a > b)
            assert run([R[1].set(a), R[2].set(b), R[0].set(R[1] <= R[2])]).r[0] == (a <= b)
            assert run([R[1].set(a), R[2].set(b), R[0].set(R[1] >= R[2])]).r[0] == (a >= b)

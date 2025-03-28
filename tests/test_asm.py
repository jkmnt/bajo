import pytest

from bajo import Label, M, Nop, R, Reg, Script
from bajo.core import Add, Comparison, ImmOffset, ImmSizeof, RhAB, Sub
from bajo.exc import DetachedLabelError, DuplicateDefError

r0 = Reg(0)
r1 = Reg(0)


def test_dup_labels():
    # duplicate labels

    # ok
    Script([Label(), Label(), Nop()]).encode()
    # not ok
    lab = Label()
    s = Script([lab, lab, Nop()])
    with pytest.raises(DuplicateDefError):
        s.encode()


def test_label_wo_instr():
    # label but no instruction to be attached

    # ok - halt is auto-added by default
    Script([Nop(), Label()]).encode()
    # not ok
    s = Script([Nop(), Label()], add_exit=False)
    with pytest.raises(DetachedLabelError):
        s.encode()


@pytest.mark.parametrize(
    ("cmp", "exp"),
    [
        (R[0] == R[0], True),
        (R[0] != R[0], False),
        (R[0] == R[1], False),
        (R[0] != R[1], True),
        #
        (M[0] == M[0], True),
        (M[0] != M[0], False),
        (M[0] == M[1], False),
        (M[0] != M[1], True),
        #
        (R[4] == M[16], True),
        (R[4] != M[16], False),
        (R[1] == M[16], False),
        (R[1] != M[16], True),
        #
        (R["a"] == R["a"], True),
        (R["a"] != R["a"], False),
        (R["a"] == R["b"], False),
        (R["a"] != R["b"], True),
        #
        (M[R[0]] == M[R[0]], True),
        (M[R[0]] == M[R[1]], False),
        (M[M[0]] == M[M[0]], True),
        (M[M[0]] == M[M[1]], False),
        (M[R[0]] == M[M[0]], True),
        (M[R[4]] == M[M[16]], True),
        (M[R[1]] == M[M[16]], False),
        #
        (M[R[0] + R[10]] == M[R[0] + R[10]], True),
        (M[R[0] + 13] == M[R[0] + 13], True),
        (M[R[0] + M[R[0] + 13]] == M[R[0] + M[R[0] + 13]], True),
        (M[R[0] + M[R[0] - 13]] == M[R[0] + M[R[0] - 13]], True),
        #
    ],
)
def test_bool_comparison(cmp, exp):
    assert isinstance(cmp, Comparison)
    assert bool(cmp) == exp


def test_bool():
    assert RhAB(Add, 1, 2) == RhAB(Add, 1, 2)
    assert RhAB(Add, 1, R[2]) == RhAB(Add, 1, R[2])
    assert RhAB(Add, 1, R[2]) == RhAB(Add, 1, M[8])
    assert RhAB(Add, 1, M[R[0] + 4]) == RhAB(Add, 1, M[R[0] + 4])
    assert RhAB(Add, 1, M[R[0] + 4]) != RhAB(Sub, 1, M[R[0] + 4])

    assert M[R[0] + M[R[0] + M[R[1] + R["lr"]]]] == M[R[0] + M[R[0] + M[R[1] + R["lr"]]]]

    a = Add(R[0], 1, 2)
    b = Add(R[0], 1, 2)
    assert a == a
    assert a != b

    assert M[ImmSizeof(a)] == M[ImmSizeof(a)]
    assert M[ImmSizeof(a)] != M[ImmSizeof(b)]
    assert M[ImmOffset(a, b)] == M[ImmOffset(a, b)]

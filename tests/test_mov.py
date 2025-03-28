import pytest

from bajo import (
    Bytes,
    Exit,
    Label,
    M,
    Mov,
    MovEq,
    MovGe,
    MovGeU,
    MovGt,
    MovGtU,
    MovLe,
    MovLeU,
    MovLt,
    MovLtU,
    MovNe,
    R,
)

from .helpers import makevm, run, u32
from .vm import BadAddrError


def test_mov():
    vm = run(
        [
            Mov(R[0], 1234),
            Mov(R[1], R[0]),
            Mov(R[1], R[1]),
        ]
    )
    assert vm.r[0] == 1234
    assert vm.r[1] == 1234


def test_condmov():
    for a in [0, 1, -1, -0x80000000, 0x7FFFFFFF]:
        for b in [0, 1, -1, -0x80000000, 0x7FFFFFFF]:
            assert run(MovEq(R[0], a, b, x=1234, y=5678)).r[0] == (1234 if a == b else 5678)
            assert run(MovNe(R[0], a, b, x=1234, y=5678)).r[0] == (1234 if a != b else 5678)
            assert run(MovGt(R[0], a, b, x=1234, y=5678)).r[0] == (1234 if a > b else 5678)
            assert run(MovGe(R[0], a, b, x=1234, y=5678)).r[0] == (1234 if a >= b else 5678)
            assert run(MovLt(R[0], a, b, x=1234, y=5678)).r[0] == (1234 if a < b else 5678)
            assert run(MovLe(R[0], a, b, x=1234, y=5678)).r[0] == (1234 if a <= b else 5678)

            assert run(MovGtU(R[0], a, b, x=1234, y=5678)).r[0] == (1234 if u32(a) > u32(b) else 5678)
            assert run(MovGeU(R[0], a, b, x=1234, y=5678)).r[0] == (1234 if u32(a) >= u32(b) else 5678)
            assert run(MovLtU(R[0], a, b, x=1234, y=5678)).r[0] == (1234 if u32(a) < u32(b) else 5678)
            assert run(MovLeU(R[0], a, b, x=1234, y=5678)).r[0] == (1234 if u32(a) <= u32(b) else 5678)


def test_load():
    v = makevm(Mov(R[0], M[511]))
    v.write_u32(511, 0xFFFFFFFE)
    v.run()
    assert v.r[0] == -2


def test_reg_based():
    v = makevm(
        [
            R[10].set(500),
            R[11].set(11),
            Mov(R[0], M[R[10] + R[11]]),
        ]
    )
    v.write_u32(511, 0xFFFFFFFE)
    v.run()
    assert v.r[0] == -2


def test_from_code():
    lab = Label()
    v = run(
        [
            Mov(R[0], M[lab]),
            Exit(),
            lab,
            Bytes.from32(-2),
        ]
    )
    assert v.r[0] == -2


def test_outside():
    # place label before the last instruction, 2 bytes.
    # manupulate offset to point just before the code end

    # ok
    lab = Label()
    run([Mov(R[0], M[lab + 2 - 4]), lab, Exit()])

    # must fail
    with pytest.raises(BadAddrError):
        lab = Label()
        run([Mov(R[0], M[lab + 2 - 3]), lab, Exit()])

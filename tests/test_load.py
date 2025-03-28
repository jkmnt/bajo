import pytest

from bajo import Bytes, Exit, Label, LdB, LdBU, LdH, LdHU, M, R
from bajo.exc import AddrError

from .helpers import makevm, no_addr_verify, run
from .vm import BadAddrError


def test_signextend():
    assert run(LdB(R[0], -2)).r[0] == -2
    assert run(LdH(R[0], -2)).r[0] == -2
    assert run(LdB(R[0], 0xFE)).r[0] == -2
    assert run(LdH(R[0], 0xFE)).r[0] == 0xFE
    assert run(LdB(R[0], 0xFFFE)).r[0] == -2
    assert run(LdH(R[0], 0xFFFE)).r[0] == -2


def test_load():
    v = makevm(
        [
            LdH(R[0], M[511]),
            LdHU(R[1], M[511]),
        ]
    )
    v.write_u16(511, 0xFFFE)
    v.run()
    assert v.r[0] == -2
    assert v.r[1] == 0xFFFE

    v = makevm(
        [
            LdB(R[0], M[511]),
            LdBU(R[1], M[511]),
        ]
    )
    v.write_u8(511, 0xFE)
    v.run()
    assert v.r[0] == -2
    assert v.r[1] == 0xFE


def test_reg_based():
    v = makevm(
        [
            R[10].set(500),
            R[11].set(11),
            LdH(R[0], M[R[10] + R[11]]),
            LdHU(R[1], M[R[10] + R[11]]),
        ]
    )
    v.write_u16(511, 0xFFFE)
    v.run()
    assert v.r[0] == -2
    assert v.r[1] == 0xFFFE

    v = makevm(
        [
            R[10].set(500),
            R[11].set(11),
            LdB(R[0], M[R[10] + R[11]]),
            LdBU(R[1], M[R[10] + R[11]]),
        ]
    )
    v.write_u8(511, 0xFE)
    v.run()
    assert v.r[0] == -2
    assert v.r[1] == 0xFE


def test_from_code():
    lab = Label()
    v = run(
        [
            LdH(R[0], M[lab]),
            LdHU(R[1], M[lab]),
            LdB(R[2], M[lab]),
            LdBU(R[3], M[lab]),
            Exit(),
            lab,
            Bytes.from32(-2),
        ]
    )
    assert v.r[0] == -2
    assert v.r[1] == 0xFFFE
    assert v.r[2] == -2
    assert v.r[3] == 0xFE


def test_outside():
    # place label before the last instruction, 2 bytes.
    # manupulate offset to point just before the code end

    # ok
    lab = Label()
    run([LdH(R[0], M[lab + 2 - 2]), lab, Exit()])
    lab = Label()
    run([LdHU(R[0], M[lab + 2 - 2]), lab, Exit()])
    lab = Label()
    run([LdB(R[0], M[lab + 2 - 1]), lab, Exit()])
    lab = Label()
    run([LdBU(R[0], M[lab + 2 - 1]), lab, Exit()])

    # vm must fail. disable the build static checks
    with no_addr_verify():
        with pytest.raises(BadAddrError):
            lab = Label()
            run([LdH(R[0], M[lab + 2 - 1]), lab, Exit()])
        with pytest.raises(BadAddrError):
            lab = Label()
            run([LdHU(R[0], M[lab + 2 - 1]), lab, Exit()])

        with pytest.raises(BadAddrError):
            lab = Label()
            run([LdB(R[0], M[lab + 2 - 0]), lab, Exit()])
        with pytest.raises(BadAddrError):
            lab = Label()
            run([LdBU(R[0], M[lab + 2 - 0]), lab, Exit()])

    # script build must fail
    with pytest.raises(BadAddrError):
        lab = Label()
        run([LdH(R[0], M[lab + 2 - 1]), lab, Exit()])
    with pytest.raises(BadAddrError):
        lab = Label()
        run([LdHU(R[0], M[lab + 2 - 1]), lab, Exit()])

    with pytest.raises(AddrError):
        lab = Label()
        run([LdB(R[0], M[lab + 2 - 0]), lab, Exit()])
    with pytest.raises(AddrError):
        lab = Label()
        run([LdBU(R[0], M[lab + 2 - 0]), lab, Exit()])

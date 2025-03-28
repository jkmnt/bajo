import pytest

from bajo import M, Mov, R, StB, StH
from bajo.exc import AddrError

from .helpers import no_addr_verify, run
from .vm import BadAddrError


def test_store():
    # simple stores, non-aligned
    vm = run(Mov(M[511], -16))  # non-aligned
    assert vm.read_s32(511) == -16
    assert vm.read_u8(510) == 0
    assert vm.read_u8(515) == 0

    vm = run(StH(M[511], -16))
    assert vm.read_s16(511) == -16
    assert vm.read_u8(510) == 0
    assert vm.read_u8(513) == 0
    assert vm.read_u8(514) == 0

    vm = run(StB(M[511], -16))
    assert vm.read_s8(511) == -16
    assert vm.read_u8(510) == 0
    assert vm.read_u8(512) == 0
    assert vm.read_u8(513) == 0
    assert vm.read_u8(514) == 0


def test_reg_based():
    vm = run([R[0].set(500), R[1].set(11), Mov(M[R[0] + R[1]], -16)])
    assert vm.read_s32(511) == -16
    assert vm.read_u8(510) == 0
    assert vm.read_u8(515) == 0

    vm = run([R[0].set(500), R[1].set(11), StH(M[R[0] + R[1]], -16)])
    assert vm.read_s16(511) == -16
    assert vm.read_u8(510) == 0
    assert vm.read_u8(513) == 0
    assert vm.read_u8(514) == 0

    vm = run([R[0].set(500), R[1].set(11), StB(M[R[0] + R[1]], -16)])
    assert vm.read_s8(511) == -16
    assert vm.read_u8(510) == 0
    assert vm.read_u8(512) == 0
    assert vm.read_u8(513) == 0
    assert vm.read_u8(514) == 0


def test_outside():
    # end of ram - ok
    run([Mov(M[1020], -16)])
    run([StH(M[1022], -16)])
    run([StB(M[1023], -16)])

    # store outside of ram - must fail
    with pytest.raises(BadAddrError):
        run([Mov(M[1021], -1234)])
    with pytest.raises(BadAddrError):
        run([StH(M[1023], -1234)])
    # disable build range check. excercise the VM
    with no_addr_verify(), pytest.raises(BadAddrError):
        run([StB(M[1024], -1234)])
    # build range
    with pytest.raises(AddrError):
        run([StB(M[1024], -1234)])

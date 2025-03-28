from contextlib import contextmanager

import pytest

import bajo.builder
from bajo import Align, Bytes, Exit, Label, M, Mov, Nop, R, Script
from bajo.env import Env
from bajo.exc import BuildError


@contextmanager
def fix_oscillations(fix: bool):
    was = bajo.builder._FIX_OSCILLATIONS
    bajo.builder._FIX_OSCILLATIONS = fix
    try:
        yield
    finally:
        bajo.builder._FIX_OSCILLATIONS = was


def _noconverge_case():
    env = Env(ram_region=(0, 1024), named_registers={}, code_region=(2030, 0xFFFFFFFF + 1))
    lab = Label()
    return Script(
        [
            R[0].set(lab),
            Mov(R[1], M[R[0]]),
            R[2].set(M[lab]),
            R[3].set(M[lab + 2]),
            Exit(),
            lab,
            Bytes.from32(-2),
            Bytes.from16(0x1234),
        ],
        env=env,
    )


def test_noconverge_exists():
    # make sure noconverge case is still reproducing
    with pytest.raises(BuildError):
        with fix_oscillations(False):
            _noconverge_case().build()
    # and fix helps
    _noconverge_case().build()


# excercise [derived from oscillating) code with different data segment offset (inserting a lot of nops).
# some of these are will oscillate too.
# make sure the solution is found in each case
@pytest.mark.skip(reason="Too long to wait. Run it manually.")
def test_noconverge_bug2():
    env = Env(ram_region=(0, 1024), named_registers={}, code_region=(1024, 0xFFFFFFFF + 1))

    for nops in range(3001, 4096):
        lab = Label()
        Script(
            [
                R[0].set(lab),
                Mov(R[1], M[R[0]]),
                R[2].set(M[lab]),
                R[3].set(M[lab + 2]),
                Exit(),
                [Nop() for i in range(nops)],
                lab,
                Bytes.from32(-2),
                Align(1),  # pack
                Bytes.from16(0x1234),
            ],
            env=env,
        ).build()


def test_noconverge_reproducible_random():
    # make sure noconverge case is still reproducing
    with pytest.raises(BuildError):
        with fix_oscillations(False):
            _noconverge_case().build()
    # and fix helps

    # make sure the choosen random is the same
    a = _noconverge_case().encode()
    b = _noconverge_case().encode()
    assert a == b

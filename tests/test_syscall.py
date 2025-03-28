from typing import Any, Callable, Sequence

import pytest

from bajo import (
    R,
    Sys,
    Sys00,
    Sys01,
    Sys02,
    Sys03,
    Sys04,
    Sys10,
    Sys11,
    Sys12,
    Sys13,
    Sys14,
    Sys20,
    Sys21,
    Sys22,
    Sys23,
    Sys24,
)

from .helpers import makevm, rands32, run
from .vm import UnknownFuncError


def create_testfunc(ret: Sequence[int], expected: Sequence[int]):
    ret = list(ret)
    expected = list(expected)

    def _f(argv: Sequence[int]):
        assert list(argv) == expected
        return tuple(ret)

    return _f


def _test_sys(retc: int, argc: int, fn=42, *, generic=False):
    rets = [rands32() for i in range(retc)]
    args = [rands32() for i in range(argc)]

    instr: Callable

    if not generic:
        if retc == 0:
            instr = [Sys00, Sys01, Sys02, Sys03, Sys04][argc]
        elif retc == 1:
            instr = [Sys10, Sys11, Sys12, Sys13, Sys14][argc]
        elif retc == 2:
            instr = [Sys20, Sys21, Sys22, Sys23, Sys24][argc]
        else:
            raise AssertionError()

        py_args: list[Any] = []

        py_args.append(fn)
        if retc:
            py_args.extend(R[i] for i in range(retc))
        py_args.extend(args)

        v = makevm(instr(*py_args))
    else:
        v = makevm(Sys(fn, tuple(R[i] for i in range(retc)), tuple(args)))

    v.funcs = {fn: create_testfunc(rets, args)}
    v.run()
    assert [v.r[i] for i in range(retc)] == list(rets)


def test_generic_syscall():
    for m in range(9):
        for n in range(8):
            for _ in range(32):
                _test_sys(m, n, generic=True)


def test_specific_syscalls():
    for m in [0, 1, 2]:
        for n in [0, 1, 2, 3, 4]:
            for _ in range(32):
                _test_sys(m, n)


def test_undef_sys():
    with pytest.raises(UnknownFuncError):
        run(Sys00(1))

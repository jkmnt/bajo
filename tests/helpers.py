from contextlib import contextmanager
from random import randint

import bajo
import bajo.builder
from bajo import Code, Script
from bajo.core import _S32_MAX, _S32_MIN, _U32_MAX

from .vm import Vm


def u32(a: int):
    return a & 0xFFFFFFFF


def s32(a: int):
    return a - 0x100000000 if a > 0x7FFFFFFF else a


def rands32():
    return randint(_S32_MIN, _S32_MAX)


def randps32():
    return randint(0, _S32_MAX)


def randu32():
    return randint(0, _U32_MAX)


def makevm(obj: Code | Script):
    if not isinstance(obj, Script):
        script = Script(obj)
    else:
        script = obj
    return Vm.from_script(script)


def run(obj: Code | Script):
    vm_ = makevm(obj)
    vm_.run()
    return vm_


@contextmanager
def u32_ok():
    was_imm = bajo.core._IMM_RANGE[:]
    bajo.core._IMM_RANGE[:] = [bajo.core._S32_MIN, bajo.core._U32_MAX + 1]
    try:
        yield
    finally:
        bajo.core._IMM_RANGE[:] = was_imm


@contextmanager
def no_addr_verify():
    was = bajo.builder._VERIFY_ADDRS
    bajo.builder._VERIFY_ADDRS = False
    try:
        yield
    finally:
        bajo.builder._VERIFY_ADDRS = was

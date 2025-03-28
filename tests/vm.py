# wrapper for C api

import sys
from ctypes import (
    CDLL,
    CFUNCTYPE,
    POINTER,
    Structure,
    c_int,
    c_int32,
    c_uint,
    c_uint32,
)
from pathlib import Path
from typing import ClassVar, Generic, Mapping, Protocol, Sequence, TypeVar

from bajo import Reg, Script

if sys.platform == "win32":
    LIBNAME = "bajo.dll"
else:
    LIBNAME = "bajo.so"
DLL = CDLL(str(Path(__file__).parent / LIBNAME))


class VmError(Exception):
    code: ClassVar[int | None] = None


# not an error really
class VmExit(VmError):
    code = 1


class BadVarintError(VmError):
    code = 2


class UnknownOpcodeError(VmError):
    code = 3


class BadOperandError(VmError):
    code = 4


class BugError(VmError):
    code = 5


class ZeroDivisionError(VmError):
    code = 6


class IntegerOverflowError(VmError):
    code = 7


# these two are local
class BadAddrError(VmError):
    code = -1


class UnknownFuncError(VmError):
    code = -2


EXC_BY_CODE: dict[int | None, type[VmError]] = {
    exc.code: exc for exc in vars().values() if isinstance(exc, type) and issubclass(exc, VmError)
}


class _Ctx(Structure):
    pass


READ_CB = CFUNCTYPE(c_uint32, POINTER(_Ctx), c_uint32, c_uint)
WRITE_CB = CFUNCTYPE(None, POINTER(_Ctx), c_uint32, c_uint32, c_uint)
CALL_CB = CFUNCTYPE(None, POINTER(_Ctx), c_int, POINTER(c_int32), POINTER(c_int32), c_uint)


# patch forward deps now
_Ctx._fields_ = [
    ("pc", c_uint32),
    ("err", c_int),
    ("exit_rc", c_int),
    ("read", READ_CB),
    ("write", WRITE_CB),
    ("call", CALL_CB),
]

DLL.bajo_step.argtypes = [POINTER(_Ctx)]
DLL.bajo_step.restype = c_int

DLL.bajo_init.argtypes = [POINTER(_Ctx), c_uint32]
DLL.bajo_init.restype = None

DLL.bajo_run.argtypes = [POINTER(_Ctx)]
DLL.bajo_run.restype = int

# my pyright thinks we're on python < 3.12 for some reason.
# fallback to using old-style Generics.

T = TypeVar("T")

T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class RPtr(Generic[T_co], Protocol):
    def __getitem__(self, idx: int) -> T_co: ...


class WPtr(Generic[T_contra], Protocol):
    def __setitem__(self, idx: int, val: T_contra) -> None: ...


class RWPtr(Generic[T], RPtr[T], WPtr[T], Protocol): ...


class SysFunc(Protocol):
    def __call__(self, argv: Sequence[int]) -> tuple[int, ...] | None: ...


class Vm:
    funcs: Mapping[int, SysFunc] = {}

    def __init__(self, code: bytes, *, ramsize=1024, codebase=1024, initial_pc=1024):
        self.code = code
        self.codebase = codebase
        self.ram = bytearray([0] * ramsize)
        self.ram_mv = memoryview(self.ram)
        self.ramsize = ramsize
        self.ctx = _Ctx()
        self.ctx.read = READ_CB(self._read)
        self.ctx.write = WRITE_CB(self._write)
        self.ctx.call = CALL_CB(self._call)
        self.initial_pc = initial_pc
        DLL.bajo_init(self.ctx, self.initial_pc)
        self.reset()

    def __getitem__(self, reg: Reg):
        return self.ram32[reg.n]

    @property
    def ram32(self):
        return self.ram_mv.cast("i")

    @property
    def ram32u(self):
        return self.ram_mv.cast("I")

    def read_s32(self, addr: int):
        return int.from_bytes(self.ram[addr : addr + 4], "little", signed=True)

    def read_u32(self, addr: int):
        return int.from_bytes(self.ram[addr : addr + 4], "big", signed=False)

    def read_s16(self, addr: int):
        return int.from_bytes(self.ram[addr : addr + 2], "little", signed=True)

    def read_u16(self, addr: int):
        return int.from_bytes(self.ram[addr : addr + 2], "big", signed=False)

    def read_s8(self, addr: int):
        return int.from_bytes(self.ram[addr : addr + 1], "little", signed=True)

    def read_u8(self, addr: int):
        return int.from_bytes(self.ram[addr : addr + 1], "big", signed=False)

    def write_s32(self, addr: int, val: int):
        self.ram[addr : addr + 4] = val.to_bytes(4, "little", signed=True)

    def write_u32(self, addr: int, val: int):
        self.ram[addr : addr + 4] = val.to_bytes(4, "little", signed=False)

    def write_s16(self, addr: int, val: int):
        self.ram[addr : addr + 2] = val.to_bytes(2, "little", signed=True)

    def write_u16(self, addr: int, val: int):
        self.ram[addr : addr + 2] = val.to_bytes(2, "little", signed=False)

    def write_s8(self, addr: int, val: int):
        self.ram[addr : addr + 1] = val.to_bytes(1, "little", signed=True)

    def write_u8(self, addr: int, val: int):
        self.ram[addr : addr + 1] = val.to_bytes(1, "little", signed=False)

    @property
    def exit_rc(self) -> int:
        return self.ctx.exit_rc

    def step(self) -> int:
        rc: int = DLL.bajo_step(self.ctx)
        if rc not in (0, 1):
            raise EXC_BY_CODE[rc](self.pc)
        return rc

    def run(self) -> int:
        rc: int = DLL.bajo_run(self.ctx)
        if rc != 1:
            raise EXC_BY_CODE[rc](self.pc)
        return self.exit_rc

    def reset(self):
        self.ram[0 : self.ramsize] = [0] * self.ramsize
        DLL.bajo_init(self.ctx, self.initial_pc)

    def _read(self, me: RWPtr[_Ctx], start: int, size: int) -> int:
        assert size
        # addresses are unsigned
        start = start & 0xFFFFFFFF
        last = (start + size - 1) & 0xFFFFFFFF

        ram = [0, self.ramsize]
        code = [self.codebase, self.codebase + len(self.code)]

        raw: bytes | bytearray

        if ram[0] <= start < ram[1] and ram[0] <= last < ram[1]:
            raw = self.ram[start - ram[0] : start - ram[0] + size]
        elif code[0] <= start < code[1] and code[0] <= last < code[1]:
            raw = self.code[start - code[0] : start - code[0] + size]
        else:
            me[0].err = BadAddrError.code
            return 0

        return int.from_bytes(raw, "little", signed=False)

    def _write(self, me: RWPtr[_Ctx], start: int, val: int, size: int) -> None:
        start = start & 0xFFFFFFFF
        last = (start + size - 1) & 0xFFFFFFFF

        val &= 0xFFFFFFFF >> (32 - size * 8)

        ram = [0, self.ramsize]

        if ram[0] <= start < ram[1] and ram[0] <= last < ram[1]:
            self.ram[start - ram[0] : start - ram[0] + size] = val.to_bytes(size, "little", signed=False)
        else:
            me[0].err = BadAddrError.code  # mem addr error or attempt to write to rom
            return

    def _call(self, me: RWPtr[_Ctx], func: int, ret: WPtr[int], args: RPtr[int], nargs: int) -> None:
        try:
            f = self.funcs[func]
        except KeyError:
            me[0].err = UnknownFuncError.code
            return
        argv = [args[i] for i in range(nargs)]
        res = f(argv)
        res = res or ()
        retc = len(res)
        for i in range(retc):
            ret[i] = res[i]

    @property
    def pc(self) -> int:
        return self.ctx.pc

    # aliases
    r = ram32
    ru = ram32u

    @classmethod
    def from_script(cls, script: Script):
        return cls(
            code=script.encode(),
            codebase=script.code_start,
            initial_pc=script.code_start,
            ramsize=script.env.ram_region[1],
        )

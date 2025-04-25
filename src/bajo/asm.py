from __future__ import annotations

from typing import Final, Iterable, Mapping, Protocol, Union, overload

from .core import (
    Add,
    IMem,
    ImmExpr,
    Inst,
    Mem,
    ProvidesLayout,
    RhAB,
    Src,
    Sub,
    fail_on_cycles,
    repr_or_fallback,
)
from .exc import AddrError

Code = Union[Inst, "Label", "Directive", None, bool, Iterable[Union[Inst, "Label", "Directive", "Code", None, bool]]]


class ProvidesLayoutAndNamedRegisters(ProvidesLayout, Protocol):
    @property
    def named_registers(self) -> Mapping[str, int]: ...


class Directive:
    pass


class Align(Directive):
    def __init__(self, n: int):
        if n < 1:
            raise ValueError("Align must be > 0", n)
        self.n: Final = n

    def __repr__(self) -> str:
        return f"Align({ self.n })"


class NoPad(Directive):
    def __repr__(self) -> str:
        return "NoPad()"


class MemAddr(Mem):
    """Memory at fixed address `addr`"""

    def __init__(self, addr: int):
        self._addr = addr

    def __repr__(self) -> str:
        return f"M[{ self._addr }]"

    def __hash__(self):
        return hash(self._addr)

    def _eq(self, other: Src):
        return isinstance(other, MemAddr) and other._addr == self._addr

    def addr_from(self, lay: ProvidesLayout, **kwargs):
        return self._addr

    def repr_for(self, lay: ProvidesLayout):
        v = self._addr
        if lay.is_code(v):
            return f"rom[{ v }]"
        return f"ram[{ v }]"


class Reg(MemAddr):
    """Register. Represents `n * 4` memory address"""

    def __init__(self, n: int):
        if n < 0:
            raise ValueError("Register number must be >= 0", n)
        super().__init__(n * 4)

    def __repr__(self) -> str:
        return f"R[{ self.n }]"

    @property
    def n(self):
        return self._addr // 4

    def repr_for(self, lay: ProvidesLayout):
        return f"r{ self.n }"

    def check_against(self, lay: ProvidesLayout) -> None:
        v = self.addr_from(lay)
        if not lay.is_ram(v):
            raise AddrError("Outside of ram region", self)


class NamedReg(Mem):
    """Named register. The concrete number is resolved during the build."""

    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"R['{ self.name }']"

    def __hash__(self):
        return hash(self.name)

    def _eq(self, other: Src):
        return isinstance(other, NamedReg) and other.name == self.name

    def addr_from(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        lay: ProvidesLayoutAndNamedRegisters,  # type: ignore[override]
    ) -> int:
        return lay.named_registers[self.name] * 4

    def check_against(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        lay: ProvidesLayoutAndNamedRegisters,  # type: ignore[override]
    ) -> None:
        v = self.addr_from(lay)
        if not lay.is_ram(v):
            raise AddrError("Outside of ram region", self)

    def repr_for(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        lay: ProvidesLayoutAndNamedRegisters,  # type: ignore[override]
    ):
        return f"r{ lay.named_registers[self.name] }"


class CodeAt(Mem):
    """Memory at instruction address, e.g. `M[label]` or `M[label + a]`"""

    def __init__(self, obj: Inst | ImmExpr):
        self.obj = obj

    def __repr__(self) -> str:
        return f"M[{ self.obj !r}]"

    def __hash__(self):
        return hash(self.obj)

    def _eq(self, other: Src) -> bool:
        return bool(self.obj == other)

    def repr_for(self, lay: ProvidesLayout):
        return f"rom[0x{ self.addr_from(lay) :x}:<{ self.obj }>]"

    def addr_from(self, lay: ProvidesLayout):
        if isinstance(self.obj, Inst):
            return self.obj.addr_from(lay)
        return self.obj.result_for(lay)

    def check_against(self, lay: ProvidesLayout) -> None:
        v = self.addr_from(lay)
        if not lay.is_code(v):
            raise AddrError("Outside of code region", self)


# Fixed data 'instruction'
class Bytes(Inst):
    """Fixed byte string to be placed in code"""

    def __init__(self, val: bytes):
        self.val = val

    def __repr__(self):
        return f"Bytes({ self.val })"

    def encode_for(self, lay: ProvidesLayout, **kwargs) -> bytes:
        return self.val

    def max_size(self) -> int:
        return len(self.val)

    @classmethod
    def from32(cls, val: int):
        return cls(val.to_bytes(4, "little", signed=val < 0x80_00_00_00))

    @classmethod
    def from16(cls, val: int):
        return cls(val.to_bytes(2, "little", signed=val < 0x80_00))

    @classmethod
    def from8(cls, val: int):
        return cls(val.to_bytes(1, "little", signed=val < 0x80))

    @classmethod
    def from_str(cls, val: str, null_terminated=True):
        s = val.encode("utf8")
        if null_terminated:
            s += b"\0"
        return cls(s)


class DataExpr(Inst):
    """Expression to be placed in code as byte string,
    e.g. DataExpr(lab + 2) places into the code address of label + 2
    """

    def __init__(self, obj: Inst | ImmExpr, size=4):
        self.obj = obj
        self._size = size

    @repr_or_fallback
    def __repr__(self):
        return f"@{ self.obj }"

    def max_size(self) -> int:
        return self._size

    @fail_on_cycles
    def encode_for(self, lay: ProvidesLayout):
        obj = self.obj
        val = obj.addr_from(lay) if isinstance(obj, Inst) else obj.result_for(lay)
        return val.to_bytes(self._size, "little")

    def repr_for(self, lay: ProvidesLayout) -> str:
        return self.encode_for(lay).hex()


class Label(ImmExpr):
    """Represents address of the following instruction."""

    _seq = 0

    def __init__(self, name: str | None = None):
        if name:
            self.name = name
        else:
            Label._seq += 1
            self.name = f"_L{ Label._seq }"

    def __repr__(self) -> str:
        return f"Label('{ self.name }')"

    def __str__(self):
        return self.name

    def result_for(self, lay: ProvidesLayout) -> int:
        return lay.addrof(self)


class RegFactory:
    @overload
    def __getitem__(self, arg: int) -> Reg: ...
    @overload
    def __getitem__(self, arg: str) -> NamedReg: ...

    def __getitem__(self, arg: int | str):
        if isinstance(arg, int):
            return Reg(arg)
        return NamedReg(arg)


class MemFactory:
    @overload
    def __getitem__(self, obj: int) -> MemAddr: ...
    @overload
    def __getitem__(self, obj: Mem | RhAB) -> IMem: ...
    @overload
    def __getitem__(self, obj: Inst | ImmExpr) -> CodeAt: ...

    # TODO: write the correct generics for RhAB type.
    # Accepting the wide type with runtime checks for now.
    def __getitem__(self, obj: Mem | RhAB | Inst | ImmExpr | int):
        if isinstance(obj, int):
            return MemAddr(obj)
        if isinstance(obj, Mem):
            return IMem(obj)
        if isinstance(obj, (Inst, ImmExpr)):
            return CodeAt(obj)
        if obj.op is Add and isinstance(obj.a, Mem) and isinstance(obj.b, Mem | IMem | int):
            return IMem(obj.a, obj.b)
        if obj.op is Sub and isinstance(obj.a, Mem) and isinstance(obj.b, int):
            return IMem(obj.a, -obj.b)
        raise TypeError("Unsupported subscription type", obj)


# This factory overrides call instead of subscription.
# TBD if it is a good api.
class DataFactory:
    @overload
    def __call__(self, obj: bytes | str | int) -> Bytes: ...

    @overload
    def __call__(self, obj: Inst | ImmExpr) -> DataExpr: ...

    def __call__(self, obj: Inst | ImmExpr | bytes | str | int):
        if isinstance(obj, str):
            return Bytes.from_str(obj)
        if isinstance(obj, int):
            return Bytes.from32(obj)
        if isinstance(obj, bytes):
            return Bytes(obj)
        return DataExpr(obj)

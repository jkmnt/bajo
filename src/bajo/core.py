from __future__ import annotations

import functools
from _thread import get_ident
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Final,
    Literal,
    Protocol,
    Sequence,
    Union,
    overload,
)

from .exc import CycleError

CmpKind = Literal["==", "!=", "<", ">", "<=", ">="]
Tgt = Union["Mem", "IMem"]
Src = Union["Mem", "IMem", "ImmExpr", int]

# The typecheckers are good at ABC checks: no need them in runtime
if TYPE_CHECKING:
    import abc

    TypecheckedABC = abc.ABC
    typechecked_abstractmethod = abc.abstractmethod
else:
    TypecheckedABC = object

    def typechecked_abstractmethod(m):
        return m


_U32_MAX = 0xFF_FF_FF_FF
_S32_MAX = 0x7F_FF_FF_FF
_S32_MIN = -0x80_00_00_00

# Allowed imm range. Monkeypatched by tests
_IMM_RANGE = [_S32_MIN, _S32_MAX + 1]

_MAX_VARINT_SIZE = 5


# This Layout protocol really should require
# addrof/sizeof only. Other fields are unused by the core
# and exposed for the asm   .py
class ProvidesLayout(Protocol):
    def addrof(self, obj: Any, /) -> int: ...
    def sizeof(self, obj: Inst, /) -> int: ...
    def is_code(self, addr: int) -> bool: ...
    def is_ram(self, addr: int) -> bool: ...


# XXX: Don't know the way to make 'otherwise' type wider.
# Erasing it's arguments type info for now.
def unless_recursive[**P, T](otherwise: Callable[..., T]) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def inner(f: Callable[P, T]) -> Callable[P, T]:
        seen: set[tuple[int, int]] = set()

        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            self = args[0]
            key = id(self), get_ident()
            if key in seen:
                return otherwise(*args, **kwargs)
            seen.add(key)
            try:
                result = f(*args, **kwargs)
            finally:
                seen.discard(key)
            return result

        functools.update_wrapper(wrapper, f)

        return wrapper

    return inner


def fallback_repr(self: object) -> str:
    return f"...{ self.__class__.__name__}"


def _ignore(*args, **kwargs):
    pass


# bytes return is here to satisfy encode_...
def raise_on_encode(self: object, *args, **kwargs) -> bytes:
    raise CycleError("Cycle detected", self)


repr_or_fallback = unless_recursive(otherwise=fallback_repr)
ignore_cycles = unless_recursive(otherwise=_ignore)
fail_on_cycles = unless_recursive(otherwise=raise_on_encode)


def check_range(val: int, range_: Sequence[int]):
    if not range_[0] <= val < range_[1]:
        raise ValueError(f"Value {val} outside of [{ range_ })")


def cast_s32(a: int):
    return a - (_U32_MAX + 1) if a > _S32_MAX else a


def _resolve_imm(a: Inst | Mem | ImmExpr | Imm, lay: ProvidesLayout) -> int:
    if isinstance(a, Imm):
        return a
    if isinstance(a, ImmExpr):
        return a.result_for(lay)
    return a.addr_from(lay)


def _ensure_not_bool(obj: Any):
    if obj is True or obj is False:
        raise TypeError("Bool operand is not allowed. Use int(val) if it's the intent")


def encode_varint(val: int):
    assert val >= 0
    nbytes = ((val.bit_length() + 6) // 7) or 1
    assert nbytes <= _MAX_VARINT_SIZE
    val = (val << nbytes) | (1 << (nbytes - 1))
    return val.to_bytes((val.bit_length() + 7) // 8, "little", signed=False)


class Inst(TypecheckedABC):
    @typechecked_abstractmethod
    def encode_for(self, lay: ProvidesLayout) -> bytes:
        raise NotImplementedError()

    @typechecked_abstractmethod
    def max_size(self) -> int:
        raise NotImplementedError()

    def size_from(self, lay: ProvidesLayout) -> int:
        return len(self.encode_for(lay))

    def addr_from(self, lay: ProvidesLayout):
        return lay.addrof(self)

    def repr_for(self, lay: ProvidesLayout) -> str:
        return repr(self)

    def check_against(self, lay: ProvidesLayout) -> None:
        pass


# NOTE: The Expr resolve is naiive and will fail on cycles.
# It's immediately visible from the tracebacks.
class ImmExpr(TypecheckedABC):
    def __add__(self, other: Inst | Mem | ImmExpr | int):
        return ImmAdd(self, other)

    def __sub__(self, other: Inst | Mem | ImmExpr | int):
        return ImmSub(self, other)

    def __mul__(self, other: Inst | Mem | ImmExpr | int):
        return ImmMul(self, other)

    def __floordiv__(self, other: Inst | Mem | ImmExpr | int):
        return ImmDiv(self, other)

    def __mod__(self, other: Inst | Mem | ImmExpr | int):
        return ImmMod(self, other)

    def __radd__(self, other: Inst | Mem | ImmExpr | int):
        return ImmAdd(other, self)

    def __rsub__(self, other: Inst | Mem | ImmExpr | int):
        return ImmSub(other, self)

    def __rmul__(self, other: Inst | Mem | ImmExpr | int):
        return ImmMul(other, self)

    def __rfloordiv__(self, other: Inst | Mem | ImmExpr | int):
        return ImmDiv(other, self)

    def __rmod__(self, other: Inst | Mem | ImmExpr | int):
        return ImmMod(other, self)

    @typechecked_abstractmethod
    def result_for(self, lay: ProvidesLayout) -> int:
        raise NotImplementedError

    def check_against(self, lay: ProvidesLayout) -> None:
        pass

    def repr_for(self, lay: ProvidesLayout):
        return f"#{ self.result_for(lay) }"

    def max_size(self) -> int:
        return _MAX_VARINT_SIZE

    @fail_on_cycles
    def encode_for(self, lay: ProvidesLayout, **kwargs):
        return Imm.encode(self.result_for(lay))


class _ImmTAB(ImmExpr):
    def __init__(self, a: Inst | Mem | ImmExpr | int, b: Inst | Mem | ImmExpr | int):
        self.a = Imm(a) if isinstance(a, int) else a
        self.b = Imm(b) if isinstance(b, int) else b

    @repr_or_fallback
    def __repr__(self):
        return f"{ self.__class__.__name__}({ self.a !r}, {self.b !r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return bool(self.a == other.a) and bool(self.b == other.b)

    @ignore_cycles
    def check_against(self, lay: ProvidesLayout) -> None:
        self.a.check_against(lay)
        self.b.check_against(lay)


class ImmAdd(_ImmTAB):
    def result_for(self, lay: ProvidesLayout):
        return _resolve_imm(self.a, lay) + _resolve_imm(self.b, lay)


class ImmSub(_ImmTAB):
    def result_for(self, lay: ProvidesLayout):
        return _resolve_imm(self.a, lay) - _resolve_imm(self.b, lay)


class ImmMul(_ImmTAB):
    def result_for(self, lay: ProvidesLayout):
        return _resolve_imm(self.a, lay) * _resolve_imm(self.b, lay)


class ImmDiv(_ImmTAB):
    def result_for(self, lay: ProvidesLayout):
        return _resolve_imm(self.a, lay) // _resolve_imm(self.b, lay)


class ImmMod(_ImmTAB):
    def result_for(self, lay: ProvidesLayout):
        return _resolve_imm(self.a, lay) % _resolve_imm(self.b, lay)


class ImmSizeof(ImmExpr):
    # NOTE: expr is for the label only.
    # arbitrary exprs are not supported
    def __init__(self, obj: Inst):
        self.obj = obj

    @repr_or_fallback
    def __repr__(self):
        return f"{ self.__class__.__name__ }({ self.obj !r})"

    def __eq__(self, other: object):
        if not isinstance(other, ImmSizeof):
            return NotImplemented
        return self.obj == other.obj

    def result_for(self, lay: ProvidesLayout):
        return lay.sizeof(self.obj)


class ImmOffset(ImmExpr):
    def __init__(self, base: Inst, tgt: Inst | Mem | ImmExpr):
        self.base = base
        self.tgt = tgt

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return bool(self.base == other.base) and bool(self.tgt == other.tgt)

    @repr_or_fallback
    def __repr__(self):
        return f"{ self.__class__.__name__ }({ self.base !r}, {self.tgt !r})"

    def repr_for(self, lay: ProvidesLayout) -> str:
        return super().repr_for(lay) + f":<{ self.tgt }>"

    def result_for(self, lay: ProvidesLayout):
        return _resolve_imm(self.tgt, lay) - (lay.addrof(self.base) + lay.sizeof(self.base))

    @ignore_cycles
    def check_against(self, lay: ProvidesLayout) -> None:
        self.base.check_against(lay)
        self.tgt.check_against(lay)


# NOTE: There is no way I know of typing such a mixin without resorting to self: Any
class RichOpsMixin:
    # to be defined in concrete class for the boolean __eq__ testing
    def _eq(self, other: Src) -> bool:
        return False

    @overload
    def __eq__(self: Any, other: Src) -> Comparison:  # type: ignore[override]
        ...

    @overload
    def __eq__(self: Any, other: object) -> bool: ...

    def __eq__(self: Any, other: object) -> Comparison | bool:
        if not isinstance(other, (Mem, IMem, ImmExpr, int)):
            return NotImplemented
        return Comparison("==", self, other, truthy=self._eq(other))

    @overload
    def __ne__(self: Any, other: Src) -> Comparison:  # type: ignore[override]
        ...

    @overload
    def __ne__(self: Any, other: object) -> bool: ...

    def __ne__(self: Any, other: object) -> Comparison | bool:
        if not isinstance(other, (Mem, IMem, ImmExpr, int)):
            return NotImplemented
        return Comparison("!=", self, other, truthy=not self._eq(other))

    # restore hashability lost by defining the __eq__ ?
    # def __hash__(self):
    #     return object.__hash__(self)

    def __lt__(self: Any, other: Src) -> Comparison:
        return Comparison("<", self, other)

    def __le__(self: Any, other: Src) -> Comparison:
        return Comparison("<=", self, other)

    def __gt__(self: Any, other: Src) -> Comparison:
        return Comparison(">", self, other)

    def __ge__(self: Any, other: Src) -> Comparison:
        return Comparison(">=", self, other)

    def __add__(self: Any, other: Src):
        return RhAB(Add, self, other)

    def __sub__(self: Any, other: Src):
        return RhAB(Sub, self, other)

    def __mul__(self: Any, other: Src):
        return RhAB(Mul, self, other)

    def __floordiv__(self: Any, other: Src):
        return RhAB(Div, self, other)

    def __truediv__(self: Any, other: Src):
        return RhAB(Div, self, other)

    def __mod__(self: Any, other: Src):
        return RhAB(Rem, self, other)

    def __lshift__(self: Any, other: Src):
        return RhAB(RShiftU, self, other)

    def __rshift__(self: Any, other: Src):
        return RhAB(RShift, self, other)

    def __and__(self: Any, other: Src):
        return RhAB(BitAnd, self, other)

    def __xor__(self: Any, other: Src):
        return RhAB(BitXor, self, other)

    def __or__(self: Any, other: Src):
        return RhAB(BitOr, self, other)

    def __neg__(self: Any):
        return RhA(Neg, self)

    def __abs__(self: Any):
        return RhA(Abs, self)

    def __invert__(self: Any):
        return RhA(Inv, self)

    def set(self: Any, rh: int | Mem | IMem | RhA | RhAB | Comparison | ImmExpr):
        if isinstance(rh, (int, Mem, IMem, ImmExpr)):
            return Mov(self, rh)
        if isinstance(rh, RhA):
            return rh.as_assign_to(self)
        if isinstance(rh, (RhAB, Comparison)):
            return rh.as_assign_to(self)
        raise TypeError("Unsupported argument", rh)


class Comparison:
    """Represents  `a op b` comparison"""

    def __init__(self, kind: CmpKind, a: Src, b: Src, truthy=False):
        self.kind: Final = kind
        self.a: Final = a
        self.b: Final = b
        self.truthy: Final = truthy

    def __bool__(self):
        return self.truthy

    @repr_or_fallback
    def __repr__(self):
        return f"{ self.a !r} { self.kind } { self.b !r}"

    def as_assign_to(self, t: Tgt) -> _TAB:
        map = {
            "==": TstEq,
            "!=": TstNe,
            "<": TstLt,
            ">": TstGt,
            "<=": TstLe,
            ">=": TstGe,
        }
        return map[self.kind](t, self.a, self.b)

    def as_if_branch_to(self, addr: Inst | Mem | ImmExpr) -> _BranchIf:
        map = {
            "==": BrEq,
            "!=": BrNe,
            "<": BrLt,
            "<=": BrLe,
            ">": BrGt,
            ">=": BrGe,
        }
        return map[self.kind](self.a, self.b, addr)

    def as_else_branch_to(self, addr: Inst | Mem | ImmExpr) -> _BranchIf:
        map = {
            "==": BrNe,
            "!=": BrEq,
            "<": BrGe,
            "<=": BrGt,
            ">": BrLe,
            ">=": BrLt,
        }
        return map[self.kind](self.a, self.b, addr)


class RhAB:
    """Represents right-hand of `t = a op b` operation"""

    def __init__(self, op: type[_TAB], a: Src, b: Src):
        self.op: Final = op
        self.a: Final = a
        self.b: Final = b

    def __eq__(self, other: object):
        if not isinstance(other, RhAB):
            return NotImplemented
        return self.op == other.op and bool(self.a == other.a) and bool(self.b == other.b)

    @repr_or_fallback
    def __repr__(self):
        return f"= { self.op !r}({ self.a !r}, { self.b !r})"

    def as_assign_to(self, t: Tgt):
        return self.op(t, self.a, self.b)


class RhA:
    """Represents right-hand of `t = a` operation"""

    def __init__(self, op: type[_TA], a: Src):
        self.op: Final = op
        self.a: Final = a

    @repr_or_fallback
    def __repr__(self):
        return f"= { self.op !r}({ self.a !r})"

    def __eq__(self, other: object):
        if not isinstance(other, RhA):
            return NotImplemented
        return self.op == other.op and bool(self.a == other.a)

    def as_assign_to(self, t: Tgt):
        return self.op(t, self.a)


class Mem(RichOpsMixin, TypecheckedABC):
    @typechecked_abstractmethod
    def addr_from(self, lay: ProvidesLayout) -> int:
        raise NotImplementedError()

    @typechecked_abstractmethod
    def repr_for(self, lay: ProvidesLayout):
        raise NotImplementedError()

    def max_size(self) -> int:
        return _MAX_VARINT_SIZE

    @fail_on_cycles
    def encode_for(self, lay: ProvidesLayout, *, as_src: bool):
        return Mem.encode(self.addr_from(lay), as_src=as_src)

    @staticmethod
    def encode(v: int, *, as_src: bool):
        assert 0 <= v < _U32_MAX + 1
        if v % 4 == 0:
            v = ((v // 4) << 2) | 0b00
        else:
            v = (v << 2) | 0b10

        if as_src:
            v = (v << 1) | 0b1

        return encode_varint(v)

    # TODO: check not only the address, but address + 3 too
    # to make sure the whole word is in range.
    # The halfword operations should check address + 1.
    @ignore_cycles
    def check_against(self, lay: ProvidesLayout) -> None:
        v = self.addr_from(lay)
        # will rise if no such address
        _ = lay.addrof(v)


# Indirect memory mode
class IMem(RichOpsMixin):
    def __init__(self, ref: Mem, offset: Mem | IMem | ImmExpr | int = 0):
        self.ref = ref
        self.offset = Imm(offset) if isinstance(offset, int) else offset

    @repr_or_fallback
    def __repr__(self) -> str:
        return f"Mem[{ self.ref !r} + { self.offset !r}]"

    # NOTE: this comparison may be wrong
    def _eq(self, other: Src) -> bool:
        if isinstance(other, IMem):
            return bool(self.ref == other.ref) and bool(self.offset == other.offset)
        return False

    def repr_for(self, lay: ProvidesLayout):
        return f"mem[{ self.ref.repr_for(lay) } + { self.offset.repr_for(lay) }]"

    def max_size(self):
        return _MAX_VARINT_SIZE + self.offset.max_size()

    @fail_on_cycles
    def encode_for(self, lay: ProvidesLayout, as_src=True):
        return IMem.encode_ref(self.ref.addr_from(lay), as_src=as_src) + self.offset.encode_for(lay, as_src=True)

    @staticmethod
    def encode_ref(v: int, as_src: bool) -> bytes:
        if v % 4 == 0:
            v = ((v // 4) << 2) | 0b01
        else:
            v = (v << 2) | 0b11
        if as_src:
            v = (v << 1) | 0b1
        return encode_varint(v)

    @ignore_cycles
    def check_against(self, lay: ProvidesLayout) -> None:
        self.ref.check_against(lay)
        self.offset.check_against(lay)


# NOTE: Imm is the subclass of int for now.
# This allows to reuse int methods.
class Imm(int):
    def repr_for(self, lay: ProvidesLayout):
        return f"#{ self }"

    def max_size(self):
        return _MAX_VARINT_SIZE

    def encode_for(self, lay: ProvidesLayout, **kwargs):
        return Imm.encode(self)

    def check_against(self, lay: ProvidesLayout) -> None:
        pass

    @staticmethod
    def encode(v: int):
        assert _S32_MIN <= v < _U32_MAX + 1
        v = cast_s32(v)
        if v >= 0:
            v = (v << 2) | 0b00
        else:
            v = (~v << 2) | 0b10
        return encode_varint(v)


class Op(Inst):
    opcode: ClassVar[int]  # provided by concrete classes
    is_vartgt: ClassVar[int] = False
    is_varsrc: ClassVar[int] = False

    def __init__(self, tgts: tuple[Tgt, ...], srcs: tuple[Src, ...]):
        # promoting ints of sources to the Imms
        srcs_: list[Mem | IMem | ImmExpr | Imm] = []
        for src in srcs:
            _ensure_not_bool(src)
            if isinstance(src, int):
                check_range(src, _IMM_RANGE)
                src = Imm(src)
            srcs_.append(src)

        self.tgts: Final = tgts
        self.srcs: Final = srcs_

    @repr_or_fallback
    def __repr__(self):
        ops = ", ".join(repr(op) for op in [*self.tgts, *self.srcs])
        return f"{self.__class__.__name__}({ops})"

    def max_size(self) -> int:
        size = 1  # mopcode
        if self.is_vartgt:
            size += _MAX_VARINT_SIZE
        size += sum([opd.max_size() for opd in self.tgts])
        if self.is_varsrc:
            size += _MAX_VARINT_SIZE
        size += sum([opd.max_size() for opd in self.srcs])
        return size

    @fail_on_cycles
    def encode_for(self, lay: ProvidesLayout) -> bytes:
        parts: list[bytes] = []

        # Trying to apply rmw optimization.
        # Comparison of operand objects may fail if they are not implementing
        # __eq__ correclty. The robust way is to compare the resulting encoding.
        is_rmw = (
            self.srcs
            and self.tgts
            and self.srcs[0].encode_for(lay, as_src=True) == self.tgts[0].encode_for(lay, as_src=True)
        )

        mop = self.opcode
        assert not (mop & 0x80)
        if is_rmw:
            mop |= 0x80

        parts.append(mop.to_bytes(1, "little", signed=False))

        if self.is_vartgt:
            parts.append(Imm.encode(len(self.tgts)))
        parts.extend([opd.encode_for(lay, as_src=False) for opd in self.tgts])
        if self.is_varsrc:
            parts.append(Imm.encode(len(self.srcs)))

        include_srcs = self.srcs[1:] if is_rmw else self.srcs
        parts.extend([opd.encode_for(lay, as_src=True) for opd in include_srcs])

        return b"".join(parts)

    def repr_for(self, lay: ProvidesLayout) -> str:
        operands: list[str] = []
        tgts = [op.repr_for(lay) for op in self.tgts]
        srcs = [op.repr_for(lay) for op in self.srcs]
        if not self.is_vartgt:
            operands.extend(tgts)
        else:
            operands.append(f"({ ', '.join([*tgts, '']) })")
        if not self.is_varsrc:
            operands.extend(srcs)
        else:
            operands.append(f"({ ', '.join([*srcs, '']) })")
        return f"{self.__class__.__name__} {', '.join(operands)}"

    @ignore_cycles
    def check_against(self, lay: ProvidesLayout) -> None:
        super().check_against(lay)
        for tgt in self.tgts:
            tgt.check_against(lay)
        for src in self.srcs:
            src.check_against(lay)


# Common signatures to reuse


class _TA(Op):
    """t = op(a)"""

    def __init__(self, t: Tgt, a: Src):
        super().__init__((t,), (a,))


class _TAB(Op):
    """t = op(a, b)"""

    def __init__(self, t: Tgt, a: Src, b: Src):
        super().__init__((t,), (a, b))

    @classmethod
    def from_ab_swap(cls, t: Tgt, a: Src, b: Src):
        return cls(t, b, a)


class _TVarSrc(Op):
    """t = op(a, b, ...)"""

    is_varsrc = True

    def __init__(self, t: Tgt, a: Src, *rest: Src):
        super().__init__((t,), (a, *rest))


# NOTE: the difference between branches and jumps in terms of code savings is minimal.
# On the other hand, branches allow position-independent code and thus preferred.
#
# The branch classes accepts the addr, not offset. User shouldn't calculate the offset manually
class _BranchIf(Op):
    def __init__(self, a: Src, b: Src, addr: Inst | Mem | ImmExpr):
        super().__init__((), (a, b, ImmOffset(self, addr)))

    @classmethod
    def from_ab_swap(cls, a: Src, b: Src, addr: Inst | Mem | ImmExpr):
        return cls(b, a, addr)


class _MoveIf(Op):
    def __init__(self, t: Tgt, a: Src, b: Src, x: Src, y: Src):
        super().__init__((t,), (a, b, x, y))

    @classmethod
    def from_ab_swap(cls, t: Tgt, a: Src, b: Src, x: Src, y: Src):
        return cls(t, b, a, x, y)

    @classmethod
    def from_xy_swap(cls, t: Tgt, a: Src, b: Src, x: Src, y: Src):
        return cls(t, a, b, y, x)


# base command set


class Nop(Op):
    """
    ---

    no operation
    """

    def __init__(self):
        super().__init__((), ())


class Add(_TAB):
    """
    t, a, b

    t = a + b
    """

    pass


class Sub(_TAB):
    """
    t, a, b

    t = a - b
    """

    pass


class Mul(_TAB):
    """
    t, a, b

    t = a * b
    """

    pass


class Div(_TAB):
    """
    t, a, b

    t = a / b

    truncating division
    """

    pass


class DivU(_TAB):
    """
    t, a, b

    t = a / b

    unsigned

    truncating division
    """

    pass


class Rem(_TAB):
    """
    t, a, b

    t = a % b

    remainder of the truncating division
    """

    pass


class RemU(_TAB):
    """
    t, a, b

    t = a % b

    unsigned

    remainder of the truncating division
    """

    pass


class And(_TVarSrc):
    """
    t, n, s[0], ..., s[n-1]

    t = s[0] && ... && s[n-1])

    result is the last arg if all args are truthy, otherwise 0
    """

    pass


class Or(_TVarSrc):
    """
    t, n, s[0], ..., s[n-1]

    t = s[0] || ... || s[n-1])

    result is the first truthy arg, otherwise 0
    """

    pass


class BitAnd(_TAB):
    """
    t, a, b

    t = a & b
    """


class BitOr(_TAB):
    """
    t, a, b

    t = a | b
    """

    pass


class BitXor(_TAB):
    """
    t, a, b

    t = a ^ b
    """

    pass


class Inv(_TA):
    """
    t, a

    t = ~a
    """

    pass


class LShift(_TAB):
    """
    t, a, b

    t = a << b

    b is limited to 32
    """

    pass


class RShift(_TAB):
    """
    t, a, b

    t = a >> b

    b is limited to 31
    """

    pass


class RShiftU(_TAB):
    """
    t, a, b

    t = a >> b

    unsigned

    b is limited to 32
    """

    pass


class TstEq(_TAB):
    """
    t, a, b

    t = a == b
    """

    pass


class TstNe(_TAB):
    """
    t, a, b

    t = a != b
    """

    pass


class TstGt(_TAB):
    """
    t, a, b

    t = a > b
    """

    pass


class TstGe(_TAB):
    """
    t, a, b

    t = a >= b
    """

    pass


class TstGtU(_TAB):
    """
    t, a, b

    t = a > b

    unsigned
    """

    pass


class TstGeU(_TAB):
    """
    t, a, b

    t = a >= b

    unsigned
    """

    pass


class Jmp(Op):
    """
    addr

    pc = addr
    """

    def __init__(self, addr: Src):
        super().__init__((), (addr,))

    def repr_for(self, lay: ProvidesLayout) -> str:
        return super().repr_for(lay) + f":<{ self.srcs[0] }>"


class JmpLnk(Op):
    """
    lr, addr

    lr = pc, pc = addr

    call
    """

    def __init__(self, lr: Tgt, addr: Src):
        super().__init__((lr,), (addr,))

    def repr_for(self, lay: ProvidesLayout) -> str:
        return super().repr_for(lay) + f":<{ self.srcs[0] }>"


#
class Br(Op):
    """
    offset

    pc += offset
    """

    def __init__(self, addr: Inst | Mem | ImmExpr):
        super().__init__((), (ImmOffset(self, addr),))


class BrLnk(Op):
    """
    lr, offset

    lr = pc, pc += offset

    call
    """

    def __init__(self, lr: Tgt, addr: Inst | Mem | ImmExpr):
        super().__init__((lr,), (ImmOffset(self, addr),))


class BrEq(_BranchIf):
    """
    a, b, offset

    if a == b then pc += offset
    """

    pass


class BrNe(_BranchIf):
    """
    a, b, offset

    if a != b then pc += offset
    """

    pass


class BrGt(_BranchIf):
    """
    a, b, offset

    if a > b then pc += offset
    """

    pass


class BrGe(_BranchIf):
    """
    a, b, offset

    if a >= b then pc += offset
    """

    pass


class BrGtU(_BranchIf):
    """
    a, b, offset

    if a > b then pc += offset

    unsigned
    """

    pass


class BrGeU(_BranchIf):
    """
    a, b, offset

    if a >= b then pc += offset

    unsigned
    """

    pass


class MovEq(_MoveIf):
    """
    t, a, b, x, y

    t = a == b ? x : y
    """

    pass


class MovGt(_MoveIf):
    """
    t, a, b, x, y

    t = a > b ? x : y
    """

    pass


class MovGe(_MoveIf):
    """
    t, a, b, x, y

    t = a >= b ? x : y
    """

    pass


class MovGtU(_MoveIf):
    """
    t, a, b, x, y

    t = a > b ? x : y

    unsigned
    """

    pass


class MovGeU(_MoveIf):
    """
    t, a, b, x, y

    t = a >= b ? x : y

    unsigned
    """

    pass


# these are special


class LdB(_TA):
    """
    t, a

    t = sign_extend(a[b7..b0])

    load byte
    """


class LdH(_TA):
    """
    t, a

    t = sign_extend(a[b15..b0])

    load halfword
    """


class LdBU(_TA):
    """
    t, a

    t = zero_extend(a[b7..b0])

    unsigned

    load byte
    """


class LdHU(_TA):
    """
    t, a

    t = zero_extend(a[b15..b0])

    unsigned

    load halfword
    """


class StB(_TA):
    """
    t, a

    t[b7..b0] = a[b7..b0]

    store byte to 8 lsbits of t. other bits are unchanged
    """

    pass


class StH(_TA):
    """
    t, a

    t[b15..b0] = a[b15..b0]

    store harfword to 16 lsbits of t. other bits are unchanged
    """

    pass


# Syscalls are not to be used directly in user code, only via some typed wrappers, e.g.
#
# def swap_time(targ: Reg, src: Reg):
#   return [Syscall11(42, targ, src)]
#
class Sys(Op):
    """
    m, t[0], ..., t[m-1], n+1, func, s[0], ..., s[n-1]

    t[0] ... t[m-1] = sysfuncs[func](s[0], ..., s[n-1])

    call host function `func` with arg vector `s` of len `n` and result vector `t` of size `m`
    """

    is_vartgt = True
    is_varsrc = True

    def __init__(self, func: int, res: tuple[Tgt, ...], arg: tuple[Src, ...]):
        super().__init__(res, (func, *arg))


class Exit(Op):
    """
    a

    exit rc = a

    sets errcode = 1 to be catched by host, sets exit rc

    """

    def __init__(self, rc: int = 0):
        super().__init__((), (rc,))


# The following instructions are redundant and may be expressed via another
# ones. But these are shorter.


class Sys00(Op):
    """
    func

    sysfuncs[func]()
    """

    def __init__(self, func: Src):
        super().__init__((), (func,))


class Sys01(Op):
    """
    func, a

    sysfuncs[func](a)
    """

    def __init__(self, func: Src, a: Src):
        super().__init__((), (func, a))


class Sys02(Op):
    """
    func, a, b

    sysfuncs[func](a, b)
    """

    def __init__(self, func: Src, a: Src, b: Src):
        super().__init__((), (func, a, b))


class Sys03(Op):
    """
    func, a, b, c

    sysfuncs[func](a, b, c)
    """

    def __init__(self, func: Src, a: Src, b: Src, c: Src):
        super().__init__((), (func, a, b, c))


class Sys04(Op):
    """
    func, a, b, c, d

    sysfuncs[func](a, b, c, d)
    """

    def __init__(self, func: Src, a: Src, b: Src, c: Src, d: Src):
        super().__init__((), (func, a, b, c, d))


class Sys10(Op):
    """
    t, func

    t = sysfuncs[func]()
    """

    def __init__(self, func: Src, t: Tgt):
        super().__init__((t,), (func,))


class Sys11(Op):
    """
    t, func, a

    t = sysfuncs[func](a)
    """

    def __init__(self, func: Src, t: Tgt, a: Src):
        super().__init__((t,), (func, a))


class Sys12(Op):
    """
    t, func, a, b

    t = sysfuncs[func](a, b)
    """

    def __init__(self, func: Src, t: Tgt, a: Src, b: Src):
        super().__init__(
            (t,),
            (func, a, b),
        )


class Sys13(Op):
    """
    t, func, a, b, c

    t = sysfuncs[func](a, b, c)
    """

    def __init__(self, func: Src, t: Tgt, a: Src, b: Src, c: Src):
        super().__init__(
            (t,),
            (
                func,
                a,
                b,
                c,
            ),
        )


class Sys14(Op):
    """
    t, func, a, b, c, d

    t = sysfuncs[func](a, b, c, d)
    """

    def __init__(self, func: Src, t: Tgt, a: Src, b: Src, c: Src, d: Src):
        super().__init__((t,), (func, a, b, c, d))


class Sys20(Op):
    """
    t, u, func

    t, u = sysfuncs[func]()
    """

    def __init__(self, func: Src, t: Tgt, u: Tgt):
        super().__init__((t, u), (func,))


class Sys21(Op):
    """
    t, u, func, a

    t, u = sysfuncs[func](a)
    """

    def __init__(self, func: Src, t: Tgt, u: Tgt, a: Src):
        super().__init__((t, u), (func, a))


class Sys22(Op):
    """
    t, u, func, a, b

    t, u = sysfuncs[func](a, b)
    """

    def __init__(self, func: Src, t: Tgt, u: Tgt, a: Src, b: Src):
        super().__init__((t, u), (func, a, b))


class Sys23(Op):
    """
    t, u, func, a, b, c

    t, u = sysfuncs[func](a, b, c)
    """

    def __init__(self, func: Src, t: Tgt, u: Tgt, a: Src, b: Src, c: Src):
        super().__init__((t, u), (func, a, b, c))


class Sys24(Op):
    """
    t, u, func, a, b, c, d

    t, u = sysfuncs[func](a, b, c, d)
    """

    def __init__(self, func: Src, t: Tgt, u: Tgt, a: Src, b: Src, c: Src, d: Src):
        super().__init__((t, u), (func, a, b, c, d))


class Mov(_TA):
    """
    t, a

    t = a
    """

    pass


class Neg(_TA):
    """
    t, a

    t = -a
    """

    pass


class Abs(_TA):
    """
    t, a

    t = abs(a)
    """

    pass


class And2(_TAB):
    """
    t, a, b

    t = a && b

    result is the last arg if all args are truthy, otherwise 0
    """

    pass


class Or2(_TAB):
    """
    t, a, b

    t = a || b

    result is the first truthy arg, otherwise 0
    """

    pass


class Max(_TVarSrc):
    """
    t, n, s[0], ..., s[n-1]

    t = max(s[0], ..., s[n-1])
    """

    pass


class Min(_TVarSrc):
    """
    t, n, s[0], ..., s[n-1]

    t = min(s[0], ..., s[n-1])
    """

    pass


class Not(_TA):
    """
    t, a

    t = ! a
    """

    pass


class Bool(_TA):
    """
    t, a

    t = !! a
    """

    pass


class LongMul(Op):
    """
    tl, th, a, b

    th:tl = a * b

    64-bit result
    """

    def __init__(self, tl: Tgt, th: Tgt, a: Src, b: Src):
        super().__init__((tl, th), (a, b))


class LongMulU(Op):
    """
    tl, th, a, b

    th:tl = a * b

    unsigned

    64-bit result
    """

    def __init__(self, tl: Tgt, th: Tgt, a: Src, b: Src):
        super().__init__((tl, th), (a, b))


# some conditional ops may be formulated via another with the arguments swapped
TstLt = TstGt.from_ab_swap
TstLe = TstGe.from_ab_swap
TstLtU = TstGtU.from_ab_swap
TstLeU = TstGeU.from_ab_swap
BrLt = BrGt.from_ab_swap
BrLe = BrGe.from_ab_swap
BrLtU = BrGtU.from_ab_swap
BrLeU = BrGeU.from_ab_swap
MovNe = MovEq.from_xy_swap
MovLt = MovGt.from_ab_swap
MovLe = MovGe.from_ab_swap
MovLtU = MovGtU.from_ab_swap
MovLeU = MovGeU.from_ab_swap


# Opcode numbers are assigned here.
# This assignment is the canonical source of truth.

# the next comment is magic. processed by scripts
# <opcodes>
Nop.opcode = 0
Add.opcode = 1
Sub.opcode = 2
Mul.opcode = 3
Div.opcode = 4
DivU.opcode = 5
Rem.opcode = 6
RemU.opcode = 7
And.opcode = 8
Or.opcode = 9
BitAnd.opcode = 10
BitOr.opcode = 11
BitXor.opcode = 12
Inv.opcode = 13
LShift.opcode = 14
RShift.opcode = 15
RShiftU.opcode = 16
TstEq.opcode = 17
TstNe.opcode = 18
TstGt.opcode = 19
TstGe.opcode = 20
TstGtU.opcode = 21
TstGeU.opcode = 22
Jmp.opcode = 23
JmpLnk.opcode = 24
Br.opcode = 25
BrLnk.opcode = 26
BrEq.opcode = 27
BrNe.opcode = 28
BrGt.opcode = 29
BrGe.opcode = 30
BrGtU.opcode = 31
BrGeU.opcode = 32
MovEq.opcode = 33
MovGt.opcode = 34
MovGe.opcode = 35
MovGtU.opcode = 36
MovGeU.opcode = 37
LdB.opcode = 38
LdH.opcode = 39
LdBU.opcode = 40
LdHU.opcode = 41
StB.opcode = 42
StH.opcode = 43
Sys.opcode = 44
Exit.opcode = 45
Sys00.opcode = 46
Sys01.opcode = 47
Sys02.opcode = 48
Sys03.opcode = 49
Sys04.opcode = 50
Sys10.opcode = 51
Sys11.opcode = 52
Sys12.opcode = 53
Sys13.opcode = 54
Sys14.opcode = 55
Sys20.opcode = 56
Sys21.opcode = 57
Sys22.opcode = 58
Sys23.opcode = 59
Sys24.opcode = 60
Mov.opcode = 61
Neg.opcode = 62
Abs.opcode = 63
And2.opcode = 64
Or2.opcode = 65
Max.opcode = 66
Min.opcode = 67
Not.opcode = 68
Bool.opcode = 69
LongMul.opcode = 70
LongMulU.opcode = 71
# </opcodes>

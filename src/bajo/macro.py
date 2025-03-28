from __future__ import annotations

from typing import Iterable, Iterator, Mapping, Sequence

from .asm import Code, Label, NamedReg, NoPad, Reg
from .core import Br, BrLnk, Comparison, IMem, Inst, Jmp, Mem
from .exc import DuplicateDefError, MissingDefError
from .script import flat_code


def when(condition: Comparison, then: Code, otherwise: Code | None = None) -> Code:
    """Generate if/else code"""
    code: Code

    if not otherwise:
        end_lab = Label()
        code = [
            condition.as_else_branch_to(end_lab),
            then,
            end_lab,
        ]
    else:
        else_lab = Label()
        end_lab = Label()
        code = [
            condition.as_else_branch_to(else_lab),
            then,
            Br(end_lab),
            else_lab,
            otherwise,
            end_lab,
        ]
    return code


def case(cases: Mapping[Comparison, Code], *, default: Code = None):
    """Generate switch-case-like code. Each case is a comparison. Only one case (or default) would be executed"""
    res: list[Code] = []
    end_label = Label()

    blocks = [(cond, code, Label()) for cond, code in cases.items()]

    # compares and branches block
    for cond, _, label in blocks:
        res.extend([cond.as_if_branch_to(label)])

    # cases blocks
    if default:
        res.extend([default, Br(end_label)])
    else:
        res.extend([Br(end_label)])
    for _, code, label in blocks:
        res.extend([label, code, Br(end_label)])

    # last jump is redundant, remove it
    if res and isinstance(res[-1], Br):
        res = res[:-1]
    res.append(end_label)
    return res


class Subroutine:
    """Subroutine macro"""

    def __init__(self, name: str | None = None):
        """Declare the Subroutine"""
        self.label = Label(name)
        self.body: Code | None = None

    def __repr__(self):
        return f"{ self.__class__.__name__ }('{ self.label.name }')"

    # this iter it the key to make Subroutine class compatible with Code
    def __iter__(self) -> Iterator[Code]:
        return self.code

    def __call__(self):
        return self.call()

    def define(self, body: Code, *, save_regs: Iterable[Reg] | None = None, is_leaf=False):
        """Define the Subroutine code"""
        if self.body is not None:
            raise DuplicateDefError("Code already defined")
        self.body = body
        self.is_leaf = is_leaf
        self.save_regs = sorted(set(save_regs or []), key=lambda x: x.n)
        return self

    @property
    def code(self) -> Iterator[Code]:
        if self.body is None:
            raise MissingDefError("Code is not defined")
        lr = NamedReg("lr")
        sp = NamedReg("sp")

        save_regs = self.save_regs

        prologue: list[Code] = []
        epilogue: list[Code] = []
        push: Sequence[Reg | NamedReg] = []
        pop: Sequence[Reg | NamedReg] = []

        jmp: Mem | IMem

        if self.is_leaf:
            if self.save_regs:
                push = save_regs
                pop = save_regs
            jmp = lr
        else:
            push = [*save_regs, lr]
            pop = save_regs
            jmp = IMem(sp, -4)

        if push:
            nregs = len(push)
            prologue = [
                sp.set(sp - nregs * 4),
                [IMem(sp, i * 4).set(reg) for i, reg in enumerate(push)],
            ]
            epilogue = [
                sp.set(sp + nregs * 4),
                [reg.set(IMem(sp, -(nregs - i) * 4)) for i, reg in enumerate(pop)],
            ]

        code: list[Code] = [self.label, *prologue, self.body, *epilogue, Jmp(jmp)]
        yield from code

    @property
    def name(self):
        return self.label.name

    def call(self) -> Code:
        return [BrLnk(NamedReg("lr"), self.label)]


def pack(code: Code):
    """Insert NoPad() before each code item"""
    flat = list(flat_code(code))
    out: list[Code] = []
    for item in flat:
        if isinstance(item, Inst):
            out.append(NoPad())
        out.append(item)
    return out

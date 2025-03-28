from functools import cached_property
from typing import Iterator, Sequence

from . import builder
from .asm import Code, Directive, Label
from .core import Exit, Inst
from .env import Env

DEF_ENV = Env(
    ram_region=(0, 0x1_00_00),
    code_region=(0x1_00_00, 0x1_00_00_00_00),
    named_registers={"sp": 13, "lr": 14},
)


def flat_code(code: Code) -> Iterator[Inst | Label | Directive | None | bool]:
    if code is None or code is False or code is True or isinstance(code, (Inst, Label, Directive)):
        yield code
    else:
        for item in code:
            yield from flat_code(item)


class Script:
    def __init__(self, code: Code, *, env: Env | None = None, add_exit=True):
        self.env = env or DEF_ENV
        self.add_exit = add_exit
        self.code = code
        self._layout: builder.BuildCtx | None = None

    def __bytes__(self):
        return self.encode()

    def __str__(self):
        return self.listing()

    def listing(self) -> str:
        lay = self.layout
        lines: list[str] = []
        all_labels = self.layout.labels_by_insts
        for inst in self.layout.insts:
            labels = all_labels.get(inst)
            if labels:
                lines.extend(f".{ label }" for label in labels)
            line = f"{ inst.addr_from(lay) :>8x}:\t{ inst.encode_for(lay).hex(' ') :24}"
            if isinstance(inst, Inst):
                line += inst.repr_for(lay)
            lines.append(line)
        return "\n".join(lines)

    @property
    def code_start(self):
        return self.env.code_region[0]

    def _code_as_list(self):
        code = [item for item in flat_code(self.code) if not (item is None or item is False or item is True)]
        last = code[-1] if code else None

        # not very robust, will miss some
        if not isinstance(last, Exit) and self.add_exit:
            code.append(Exit())
        return code

    def build(self):
        return self.layout

    @cached_property
    def layout(self) -> builder.BuildCtx:
        code = self._code_as_list()
        builder.check(code)
        return builder.build(code, self.env)

    @property
    def result(self) -> Sequence[Inst]:
        return self.layout.insts

    def encode(self) -> bytes:
        if not self.result:
            return b""
        bytecodes = [inst.encode_for(self.layout) for inst in self.result]
        res = b"".join(bytecodes)
        # Doublechecking result len to by safe
        end = self.result[-1].addr_from(self.layout) + len(bytecodes[-1])
        start = self.env.code_region[0]
        if start + len(res) != end:
            raise AssertionError("Bytecode size mismatch", len(res), end - start)
        return res

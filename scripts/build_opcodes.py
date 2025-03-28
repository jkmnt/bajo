# process instructions and create C header and markdown doc table

from typing import Any, TypeGuard

from bajo import core

Instr = type[core.Op]


def camel_to_snake(s: str):
    return "".join(["_" + c.lower() if c.isupper() else c for c in s]).strip("_")


def is_instr(item: Any) -> TypeGuard[Instr]:
    if not isinstance(item, type):
        return False
    if not issubclass(item, core.Op):
        return False
    if item is core.Op:
        return False
    if item.__name__.startswith("_"):
        return False
    return True


def grep_instrs():
    instrs: list[Instr] = [item for item in vars(core).values() if is_instr(item)]
    return instrs


def check_instrs(instrs: list[Instr]):
    opset = {inst.opcode for inst in instrs}
    assert len(opset) == len(instrs)
    assert all(isinstance(op, int) and op >= 0 for op in opset)


def escape_md(s: str):
    specials = R"\*_{}[]()#+-.!|"
    for c in specials:
        s = s.replace(c, f"\\{ c }")
    return s


def md_highlight(*lines: str):
    out = []
    for line in lines:
        line = line.replace("unsigned", "_unsigned_")
        out.append(line)
    return out


def create_md(instrs: list[Instr]):
    rows = []
    for instr in instrs:
        doc = instr.__doc__
        assert doc is not None
        attrs = [escape_md(attr) for line in doc.splitlines() if (attr := line.strip())]
        operands, *actions = attrs
        actions = md_highlight(*actions)
        row = f"| { instr.__name__ } | { instr.opcode } | { operands } | {'<br>'.join(actions)} |"
        rows.append(row)

    header = [
        "| Name | Code | Operands | Action |",
        "|---|---|---|---|",
    ]

    return f"""\
# VM instructions

{"\n".join([*header, *rows])}
"""


def create_h(instrs: list[Instr]):
    instrs = sorted(instrs, key=lambda x: x.opcode)
    lines: list[str] = []
    for instr in instrs:
        # comment = (instr.__doc__ or "").strip().splitlines()[0]
        line = f"    {camel_to_snake(instr.__name__).upper()} = { instr.opcode },"
        lines.append(line)

    return f"""
#ifndef _OPCODES_H_
#define _OPCODES_H_

#define _MAX_OPCODE { instrs[-1].opcode}

typedef enum
{{
{ "\n".join(lines) }
}} opcode_t;

#endif
    """


def main():
    instrs = grep_instrs()
    check_instrs(instrs)
    with open("../docs/opcodes.md", "w") as f:
        f.write(create_md(instrs))
    with open("../c/opcodes.h", "w") as f:
        f.write(create_h(instrs))


if __name__ == "__main__":
    main()

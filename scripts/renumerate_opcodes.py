import re

from build_opcodes import grep_instrs


def main():
    instrs = grep_instrs()
    for i, instr in enumerate(instrs):
        instr.opcode = i

    assigns = "\n".join(f"{inst.__name__}.opcode = { inst.opcode }" for inst in instrs)
    # exports = ",\n".join(f'    "{inst.__name__}"' for inst in instrs)

    res = f"""\
# <opcodes>
{ assigns }
# </opcodes>
"""

    fn = "../src/bajo/core.py"

    with open(fn) as f:
        was = f.read()

    repl = re.sub("(# <opcodes>)$(.*)(# </opcodes>)", lambda m: res, was, count=1, flags=re.DOTALL | re.MULTILINE)

    with open(fn, "w") as f:
        f.write(repl)


if __name__ == "__main__":
    main()

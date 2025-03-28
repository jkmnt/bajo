import ast
import re
from pathlib import Path

file = Path("../src/bajo/__init__.py")
was = file.read_text()

tree = ast.parse(was)

res = []
for item in ast.walk(tree):
    if isinstance(item, ast.ImportFrom):
        res.extend([name.name for name in item.names])

items = "\n".join(f'    "{ r }",' for r in sorted(res))

all_ = f"""\
__all__ = [
{ items }
]"""

now = re.sub(r"__all__ = \[.*?\]", all_, was, count=1, flags=re.DOTALL)

file.write_text(now)

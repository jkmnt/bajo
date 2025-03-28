import pytest

import bajo
from bajo.env import Env


# The "memoryview" of the default 64k is seems to be slow in Python.
# Patching the default to use 1k.
@pytest.fixture(scope="session", autouse=True)
def script_env():
    was = bajo.script.DEF_ENV
    bajo.script.DEF_ENV = Env(
        ram_region=(0, 1024),
        code_region=(0x10_00_00, 0xFF_FF_FF_FF + 1),
        named_registers={"sp": 13, "lr": 14},
    )
    yield
    bajo.script.DEF_ENV = was

# C interpreter API

## Functions

```c
void bajo_init(bajo_t *me, uint32_t pc);
int bajo_step(bajo_t *me);
int bajo_run(bajo_t *me);
```

- init

  Set the program counter to the `pc`, clear the error.

- step

  Execute a single instruction. Returns the rc.

- run

  Run until an error (or an exit). Returns the rc.

## Context

```c
struct bajo_t
{
    // Program counter
    uint32_t pc;
    // bajo_err_e or interface error code
    int err;
    // Exit instruction rc code
    int exit_rc;
    // Host api callbacks:
    // Read 1, 2, 3, or 4-byte integer from `addr`.
    // Little-endian.
    uint32_t (*read)(bajo_t *me, uint32_t addr, unsigned int len);
    // Write 1, 2, 3, or 4 bytes of integer `val` to `addr`.
    // Little-endian.
    void (*write)(bajo_t *me, uint32_t addr, uint32_t val, unsigned int len);
    // Call host function with number `fn`.
    void (*call)(bajo_t *me, int fn, int32_t *res, const int32_t *args, unsigned int nargs);
};
```

Interface functions `read`, `write`, `call` must be set by user code. Other fields are initialized by the `bajo_init`.

Context may be "inherited" to carry additional app-specific data.

```c
typedef struct
{
    bajo_t base;
    int my_var;
    int *my_ptr;
    int code_size;
} debajo_t;

uint8_t ram[1024];
uint8_t rom[1024];

f = fopen("script.bin", "rb");
fread(rom, 1, code_size, f);

debajo_t debajo =
{
    .base =
    {
        .read = my_read, // reads ram, rom
        .write = my_write, // writes ram
        .call = my_call,
    },
    .my_var = 42,
    .my_ptr = NULL,
    .code_size = code_size,
};

bajo_init(&debajo->base);
```

## Callbacks

Examples are presented in Python-like
pseudocode. Errors should be reported
by setting `me->err`.

### Read

Read a 1, 2, 3, or 4-byte little-endian integer from the `addr`.

```python
def read(me, addr, size):
    if in_ram_range(addr, addr+size):  # read ram
        return int.from_bytes(ram[addr:addr+size])
    elif in_code_range(addr, addr+size): # read code
        return int.from_bytes(code[addr:addr+size])
    else:    # address error
        me.err = -1
        return 0
```

### Write

Write 1, 2, 3, or 4 bytes of the little-endian integer `val` to the `addr`.

```python
def write(me, addr, val, size):
    if in_ram_range(addr, addr+size):   # write to ram
        ram[addr:addr+size] = val.to_bytes(size)
    else:
        me.err = -1;
```

### Call

Call the host function `fn` with `args` arguments.
Store the result in the `res`.

```python
def call(me, fn, res, args, nargs):
    if fn == 1: # 1 ret, 2 args
        res[0] = host_func_1(args[0], args[1])
    elif fn == 2: # 0 rets, 1 arg
        host_func_2(args[0])
    elif fn == 3: # 2 rets, 0 args
        result = host_func_3()
        res[0] = result.a
        res[1] = result.b
    elif fn == 4:    # 1 ret, 0 args. Optionally rising VM error.
        result = host_func_4()
        if result.ok:
            res[0] = 1
        else:
            me.err = -1234;
    else:   # unknown function
        me.err = -2
```

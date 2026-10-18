"""Who touches each RAM byte: trace the ROM's code and list every read and write of $80-$FF.

A small 6502 tracer of our own, so the answer comes from the ROM itself rather than from the hand-edited
disassembly. It starts at the reset vector, follows every branch, jump and subroutine call, and records each
instruction it reaches. Bytes it never reaches are data (tables, sprites) - that split is the first map of
the ROM's elements.

Writes docs/generated/ram-xref.md (per RAM byte: its name and meaning from game/ram_map.py, how sure we
are, and which routines read and write it) and
docs/generated/rom-layout.md (the ROM as runs of code and data).

Usage: python tools/xref.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import HERE, ROM  # noqa: E402

sys.path.insert(0, HERE)
from game import ram_map  # noqa: E402

Instruction = tuple[str, str, int | None, int]   # (mnemonic, addressing mode, operand, length in bytes)
Access = tuple[int, int, str, str]   # (instruction address, its routine, mnemonic, how: read / write...)

ROM_START = 0xF000
GENERATED = os.path.join(HERE, "docs", "generated")

# 6502 addressing modes -> instruction length in bytes
LENGTH = {"imp": 1, "acc": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2, "izx": 2, "izy": 2, "rel": 2,
          "abs": 3, "abx": 3, "aby": 3, "ind": 3}

# opcode -> (mnemonic, mode), the documented 6502 instructions
OPCODES: dict[int, tuple[str, str]] = {}
_TABLE = """
00 BRK imp|01 ORA izx|05 ORA zp|06 ASL zp|08 PHP imp|09 ORA imm|0A ASL acc|0D ORA abs|0E ASL abs
10 BPL rel|11 ORA izy|15 ORA zpx|16 ASL zpx|18 CLC imp|19 ORA aby|1D ORA abx|1E ASL abx
20 JSR abs|21 AND izx|24 BIT zp|25 AND zp|26 ROL zp|28 PLP imp|29 AND imm|2A ROL acc|2C BIT abs|2D AND abs
2E ROL abs|30 BMI rel|31 AND izy|35 AND zpx|36 ROL zpx|38 SEC imp|39 AND aby|3D AND abx|3E ROL abx
40 RTI imp|41 EOR izx|45 EOR zp|46 LSR zp|48 PHA imp|49 EOR imm|4A LSR acc|4C JMP abs|4D EOR abs|4E LSR abs
50 BVC rel|51 EOR izy|55 EOR zpx|56 LSR zpx|58 CLI imp|59 EOR aby|5D EOR abx|5E LSR abx
60 RTS imp|61 ADC izx|65 ADC zp|66 ROR zp|68 PLA imp|69 ADC imm|6A ROR acc|6C JMP ind|6D ADC abs|6E ROR abs
70 BVS rel|71 ADC izy|75 ADC zpx|76 ROR zpx|78 SEI imp|79 ADC aby|7D ADC abx|7E ROR abx
81 STA izx|84 STY zp|85 STA zp|86 STX zp|88 DEY imp|8A TXA imp|8C STY abs|8D STA abs|8E STX abs
90 BCC rel|91 STA izy|94 STY zpx|95 STA zpx|96 STX zpy|98 TYA imp|99 STA aby|9A TXS imp|9D STA abx
A0 LDY imm|A1 LDA izx|A2 LDX imm|A4 LDY zp|A5 LDA zp|A6 LDX zp|A8 TAY imp|A9 LDA imm|AA TAX imp
AC LDY abs|AD LDA abs|AE LDX abs|B0 BCS rel|B1 LDA izy|B4 LDY zpx|B5 LDA zpx|B6 LDX zpy|B8 CLV imp
B9 LDA aby|BA TSX imp|BC LDY abx|BD LDA abx|BE LDX aby
C0 CPY imm|C1 CMP izx|C4 CPY zp|C5 CMP zp|C6 DEC zp|C8 INY imp|C9 CMP imm|CA DEX imp|CC CPY abs
CD CMP abs|CE DEC abs|D0 BNE rel|D1 CMP izy|D5 CMP zpx|D6 DEC zpx|D8 CLD imp|D9 CMP aby|DD CMP abx
DE DEC abx|E0 CPX imm|E1 SBC izx|E4 CPX zp|E5 SBC zp|E6 INC zp|E8 INX imp|E9 SBC imm|EA NOP imp
EC CPX abs|ED SBC abs|EE INC abs|F0 BEQ rel|F1 SBC izy|F5 SBC zpx|F6 INC zpx|F8 SED imp|F9 SBC aby
FD SBC abx|FE INC abx
"""
for _entry in _TABLE.replace("\n", "|").split("|"):
    if _entry.strip():
        _code, _mnemonic, _mode = _entry.split()
        OPCODES[int(_code, 16)] = (_mnemonic, _mode)

WRITES = {"STA", "STX", "STY", "INC", "DEC", "ASL", "LSR", "ROL", "ROR"}
READ_AND_WRITE = {"INC", "DEC", "ASL", "LSR", "ROL", "ROR"}
ENDS_FLOW = {"RTS", "RTI", "BRK", "JMP"}
BRANCHES = {"BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ"}
# A branch that follows a load of a known constant always goes the same way (the 2600 trick for a
# 2-byte "jump"); the tracer must not fall through into whatever data follows it.
ALWAYS_TAKEN = {"BNE": lambda value: value != 0, "BEQ": lambda value: value == 0,
                "BPL": lambda value: value < 0x80, "BMI": lambda value: value >= 0x80}


def read_rom() -> bytes:
    with open(ROM, "rb") as rom_file:
        return rom_file.read()


def decode(rom: bytes, address: int) -> Instruction | None:
    """The instruction at address: (mnemonic, mode, operand value, length), or None if it isn't one."""
    opcode = rom[address - ROM_START]
    if opcode not in OPCODES:
        return None
    mnemonic, mode = OPCODES[opcode]
    length = LENGTH[mode]
    operand: int | None = None
    if length == 2:
        operand = rom[address - ROM_START + 1]
        if mode == "rel":   # a branch (always 2 bytes): the operand is an offset from the next instruction
            offset = operand - 256 if operand >= 0x80 else operand
            operand = address + 2 + offset
    elif length == 3:
        operand = rom[address - ROM_START + 1] | rom[address - ROM_START + 2] << 8
    return mnemonic, mode, operand, length


def trace(rom: bytes) -> tuple[dict[int, Instruction], set[int]]:
    """Follow the code from the reset vector. Returns {address: instruction} and the set of JSR targets."""
    reset = rom[0xFFC] | rom[0xFFD] << 8
    to_visit = [reset]
    instructions: dict[int, Instruction] = {}
    subroutines = {reset}
    while to_visit:
        address = to_visit.pop()
        last_constant: int | None = None
        while ROM_START <= address < 0x10000 and address not in instructions:
            instruction = decode(rom, address)
            if instruction is None:
                break
            instructions[address] = instruction
            mnemonic, mode, operand, length = instruction
            if mnemonic in ("JSR", "JMP") and mode == "abs" and operand is not None:
                to_visit.append(operand)
                if mnemonic == "JSR":
                    subroutines.add(operand)
            if mnemonic in BRANCHES and operand is not None:
                to_visit.append(operand)
                if always_taken(mnemonic, last_constant):
                    break
            if mnemonic in ENDS_FLOW:
                break
            last_constant = constant_loaded(mnemonic, mode, operand, last_constant)
            address += length
    return instructions, subroutines


def always_taken(mnemonic: str, last_constant: int | None) -> bool:
    if mnemonic not in ALWAYS_TAKEN or last_constant is None:
        return False
    return ALWAYS_TAKEN[mnemonic](last_constant)


def constant_loaded(mnemonic: str, mode: str, operand: int | None, previous: int | None) -> int | None:
    """The value the flags now reflect, if an instruction just loaded a constant; else None."""
    if mnemonic in ("LDA", "LDX", "LDY") and mode == "imm":
        return operand
    if mnemonic.startswith("ST") or mnemonic in ("CLC", "SEC", "CLD", "SED"):
        return previous  # these leave N and Z alone
    return None


def ram_accesses(instructions: dict[int, Instruction], subroutines: set[int]) -> dict[int, list[Access]]:
    """{ram address: [(instruction address, routine, mnemonic, how)]} for every $80-$FF access."""
    accesses: dict[int, list[Access]] = {}
    routine_starts = sorted(subroutines)
    for address in sorted(instructions):
        mnemonic, mode, operand, _length = instructions[address]
        if mode not in ("zp", "zpx", "zpy", "izx", "izy") or operand is None or operand < 0x80:
            continue
        routine = max((start for start in routine_starts if start <= address), default=address)
        how = access_kind(mnemonic, mode)
        for ram_address in touched(mode, operand):
            accesses.setdefault(ram_address, []).append((address, routine, mnemonic, how))
    return accesses


def access_kind(mnemonic: str, mode: str) -> str:
    if mode in ("izx", "izy"):
        return "pointer"
    if mnemonic in READ_AND_WRITE:
        return "read+write"
    if mnemonic in WRITES:
        return "write"
    return "read"


def touched(mode: str, operand: int) -> list[int]:
    if mode in ("izx", "izy"):
        return [operand, operand + 1]  # a pointer: low byte, high byte
    return [operand]


def describe_access(mnemonic: str, mode: str, how: str) -> str:
    index = {"zpx": ",X", "zpy": ",Y", "izy": " (pointer),Y", "izx": " (pointer,X)"}.get(mode, "")
    return f"{mnemonic}{index}"


def write_xref(accesses: dict[int, list[Access]], instructions: dict[int, Instruction]) -> str:
    lines = ["# RAM map and cross-reference (generated by tools/xref.py - do not edit)", "",
             "Name, meaning and how sure we are come from game/ram_map.py (live = checked in the running",
             "game by tools/verify_ram.py; code = read from the code; guess = a working idea). The last two",
             "columns are every instruction in the ROM that touches the byte, found by tracing the code from",
             "the reset vector. `,X` means the byte is the base of a table the code indexes into, so the",
             "bytes after it are touched too. Routines are named by their address ($Fxxx).", "",
             "| RAM | name | meaning | sure | written by | read by |", "|---|---|---|---|---|---|"]
    for ram_address in range(0x80, 0x100):
        name, meaning, sure = ram_map.describe(ram_address)
        if ram_address not in ram_map.RAM:
            meaning = "(part of the table above)"
        found = accesses.get(ram_address, [])
        writers = summarise(found, instructions, ("write", "read+write"))
        readers = summarise(found, instructions, ("read", "read+write", "pointer"))
        lines.append(f"| ${ram_address:02X} | {name} | {meaning} | {sure} | {writers} | {readers} |")
    path = os.path.join(GENERATED, "ram-xref.md")
    with open(path, "w") as out:
        out.write("\n".join(lines) + "\n")
    return path


def summarise(found: list[Access], instructions: dict[int, Instruction], kinds: tuple[str, ...]) -> str:
    by_routine: dict[int, set[str]] = {}
    for address, routine, mnemonic, how in found:
        if how not in kinds:
            continue
        _mnemonic, mode, _operand, _length = instructions[address]
        label = describe_access(mnemonic, mode, how)
        by_routine.setdefault(routine, set()).add(label)
    parts = [f"{routine:04X} ({', '.join(sorted(labels))})" for routine, labels in sorted(by_routine.items())]
    return "<br>".join(parts) if parts else ""


def write_layout(rom: bytes, instructions: dict[int, Instruction]) -> str:
    """The ROM as alternating runs of code and data."""
    is_code = [False] * len(rom)
    for address, (_mnemonic, _mode, _operand, length) in instructions.items():
        for offset in range(length):
            is_code[address - ROM_START + offset] = True
    runs = []
    start = 0
    for index in range(1, len(rom) + 1):
        if index == len(rom) or is_code[index] != is_code[start]:
            runs.append((start, index - 1, is_code[start]))
            start = index
    lines = ["# ROM layout (generated by tools/xref.py - do not edit)", "",
             "Which bytes the tracer reached as code; everything else is data (tables, sprites, playfield).",
             f"Code: {sum(is_code)} bytes. Data: {len(rom) - sum(is_code)} bytes.", "",
             "| from | to | bytes | kind |", "|---|---|---|---|"]
    for first, last, code in runs:
        kind = "code" if code else "data"
        lines.append(f"| ${first + ROM_START:04X} | ${last + ROM_START:04X} | {last - first + 1} | {kind} |")
    path = os.path.join(GENERATED, "rom-layout.md")
    with open(path, "w") as out:
        out.write("\n".join(lines) + "\n")
    return path


def main() -> None:
    os.makedirs(GENERATED, exist_ok=True)
    rom = read_rom()
    instructions, subroutines = trace(rom)
    accesses = ram_accesses(instructions, subroutines)
    print(write_xref(accesses, instructions))
    print(write_layout(rom, instructions))
    untouched = [f"${address:02X}" for address in range(0x80, 0x100) if address not in accesses]
    print(f"{len(instructions)} instructions, {len(subroutines)} subroutines")
    print("RAM no instruction names directly:", " ".join(untouched))


if __name__ == "__main__":
    main()

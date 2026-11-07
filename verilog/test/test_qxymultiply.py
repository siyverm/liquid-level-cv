# claude sonnet 5.5
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

DW = int(os.environ.get("DATA_WIDTH", 16))
FB = int(os.environ.get("FRAC_BITS", 8))
WW = int(os.environ.get("WEIGHT_WIDTH", DW))
WFB = int(os.environ.get("WEIGHT_FRAC_BITS", FB))

LATENCY = 4  # clock edges from input applied to result visible (a/b, product, product_out, final)


def model(a, b):
    """Exact product, round half up, arithmetic shift (Python >> floors, like >>>)."""
    return ((a * b) + (1 << (WFB - 1))) >> WFB


def u(x, w):
    """Two's-complement encode x into w bits for driving a signed port."""
    return x & ((1 << w) - 1)


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.en.value = 1
    dut.input_reg.value = 0
    dut.weight.value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await Timer(1, "ns")
    assert dut.final_product.value.signed_integer == 0, "output not cleared by reset"
    dut.rst_n.value = 1


async def run_vectors(dut, vecs):
    """Stream one (a, b) pair per cycle; return outputs aligned to the input order."""
    n = len(vecs)
    outs = []
    for e in range(n + LATENCY - 1):
        a, b = vecs[e] if e < n else (0, 0)
        dut.input_reg.value = u(a, DW)
        dut.weight.value = u(b, WW)
        await RisingEdge(dut.clk)
        await Timer(1, "ns")  # let registers settle before reading
        if e >= LATENCY - 1:
            outs.append(dut.final_product.value.signed_integer)
    return outs


def check(vecs, outs):
    assert len(outs) == len(vecs)
    for i, ((a, b), got) in enumerate(zip(vecs, outs)):
        exp = model(a, b)
        assert got == exp, f"vec {i}: a={a} b={b} got={got} expected={exp}"


@cocotb.test()
async def test_unity(dut):
    """1.0 * 1.0 should come out as 1.0 in the input's Q format."""
    await setup(dut)
    one_a, one_b = 1 << FB, 1 << WFB
    outs = await run_vectors(dut, [(one_a, one_b), (-one_a, one_b), (0, one_b)])
    assert outs == [1 << FB, -(1 << FB), 0], outs


@cocotb.test()
async def test_corners(dut):
    await setup(dut)
    amin, amax = -(1 << (DW - 1)), (1 << (DW - 1)) - 1
    bmin, bmax = -(1 << (WW - 1)), (1 << (WW - 1)) - 1
    vecs = [(a, b) for a in (amin, -1, 0, 1, amax) for b in (bmin, -1, 0, 1, bmax)]
    check(vecs, await run_vectors(dut, vecs))


@cocotb.test()
async def test_random(dut):
    await setup(dut)
    rng = random.Random(1234)
    vecs = [
        (
            rng.randint(-(1 << (DW - 1)), (1 << (DW - 1)) - 1),
            rng.randint(-(1 << (WW - 1)), (1 << (WW - 1)) - 1),
        )
        for _ in range(2000)
    ]
    check(vecs, await run_vectors(dut, vecs))


@cocotb.test()
async def test_enable_stall(dut):
    """With en=0 the whole pipeline must freeze and ignore inputs."""
    await setup(dut)
    X, Y = (3 << FB, -(5 << WFB) // 2), (-(7 << FB), 2 << WFB)

    async def hold(vec, cycles):
        dut.input_reg.value = u(vec[0], DW)
        dut.weight.value = u(vec[1], WW)
        for _ in range(cycles):
            await RisingEdge(dut.clk)
        await Timer(1, "ns")
        return dut.final_product.value.signed_integer

    assert await hold(X, LATENCY) == model(*X)
    dut.en.value = 0
    assert await hold(Y, 6) == model(*X), "pipeline advanced while en=0"
    dut.en.value = 1
    assert await hold(Y, LATENCY) == model(*Y), "pipeline did not resume"
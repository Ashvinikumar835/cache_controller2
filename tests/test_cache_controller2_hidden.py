from __future__ import annotations
import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb_tools.runner import get_runner


# ============================================================
# DRIVER UTILITIES
# ============================================================

async def reset_dut(dut):
    dut.rst_n.value = 0
    dut.req_valid.value = 0
    dut.mem_ready.value = 0

    for _ in range(5):
        await RisingEdge(dut.clk)

    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def send_request(dut, rw, addr, wdata=0):
    dut.req_valid.value = 1
    dut.req_rw.value = rw
    dut.req_addr.value = addr
    dut.req_wdata.value = wdata

    await RisingEdge(dut.clk)
    dut.req_valid.value = 0


async def wait_for_response(dut, cycles=20):
    for _ in range(cycles):
        await RisingEdge(dut.clk)
        if dut.resp_valid.value == 1:
            return int(dut.resp_rdata.value)
    return None


# ============================================================
# MEMORY MODEL
# ============================================================

async def memory_model(dut):
    stall = 0

    while True:
        await RisingEdge(dut.clk)
        dut.mem_ready.value = 0

        if dut.mem_req_valid.value == 1:
            stall += 1

            if stall % 4 == 0:
                dut.mem_ready.value = 1

                if dut.mem_req_rw.value == 0:
                    dut.mem_rdata.value = (
                        0xBEEF0000 | (int(dut.mem_addr.value) & 0xFFFF)
                    )


# ============================================================
# COMMON SETUP
# ============================================================

async def setup_dut(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start(start_high=False))
    cocotb.start_soon(memory_model(dut))

    dut.req_valid.value = 0
    dut.req_rw.value = 0
    dut.req_addr.value = 0
    dut.req_wdata.value = 0
    dut.mem_ready.value = 0
    dut.mem_rdata.value = 0

    await reset_dut(dut)


# ============================================================
# TESTS
# ============================================================

@cocotb.test()
async def test_read_hit(dut):
    await setup_dut(dut)

    dut.valid.value = 1
    dut.tag.value   = 0x00100
    dut.data.value  = 0xA5A5A5A5
    dut.dirty.value = 0

    await RisingEdge(dut.clk)

    await send_request(dut, 0, (0x00100 << 12))
    data = await wait_for_response(dut)

    assert data == 0xA5A5A5A5


@cocotb.test()
async def test_write_hit(dut):
    await setup_dut(dut)

    dut.valid.value = 1
    dut.tag.value   = 0x00100
    dut.data.value  = 0xA5A5A5A5
    dut.dirty.value = 0

    await RisingEdge(dut.clk)

    await send_request(dut, 1, (0x00100 << 12), 0xDEADBEEF)

    for _ in range(5):
        await RisingEdge(dut.clk)

    assert int(dut.data.value) == 0xDEADBEEF
    assert int(dut.dirty.value) == 1


@cocotb.test()
async def test_multiple_writes(dut):
    await setup_dut(dut)

    dut.valid.value = 1
    dut.tag.value   = 0x00100
    dut.data.value  = 0
    dut.dirty.value = 0

    await RisingEdge(dut.clk)

    await send_request(dut, 1, (0x00100 << 12), 0x11111111)
    await RisingEdge(dut.clk)

    await send_request(dut, 1, (0x00100 << 12), 0x22222222)

    for _ in range(3):
        await RisingEdge(dut.clk)

    assert int(dut.data.value) == 0x22222222


@cocotb.test()
async def test_clean_miss(dut):
    await setup_dut(dut)

    dut.valid.value = 0
    dut.dirty.value = 0

    await send_request(dut, 0, 0x00002000)
    data = await wait_for_response(dut, 30)

    assert data is not None


@cocotb.test()
async def test_dirty_miss(dut):
    await setup_dut(dut)

    dut.valid.value = 1
    dut.dirty.value = 1
    dut.tag.value   = 0x00100
    dut.data.value  = 0xAAAA5555

    await send_request(dut, 0, (0x00200 << 12))

    writeback_seen = False
    response_seen  = False

    for _ in range(30):
        await RisingEdge(dut.clk)

        if dut.mem_req_valid.value and dut.mem_req_rw.value:
            writeback_seen = True

        if dut.resp_valid.value:
            response_seen = True

    assert writeback_seen and response_seen


@cocotb.test()
async def test_clean_miss_variant(dut):
    await setup_dut(dut)

    dut.valid.value = 0
    dut.dirty.value = 0

    await send_request(dut, 0, 0x00010000)
    data = await wait_for_response(dut, 30)

    assert data is not None


@cocotb.test()
async def test_dirty_miss_variant(dut):
    await setup_dut(dut)

    dut.valid.value = 1
    dut.dirty.value = 1
    dut.tag.value   = 0x00100
    dut.data.value  = 0xAAAA5555

    await send_request(dut, 0, (0x00200 << 9))

    writeback_seen = False
    response_seen  = False

    for _ in range(30):
        await RisingEdge(dut.clk)

        if dut.mem_req_valid.value and dut.mem_req_rw.value:
            writeback_seen = True

        if dut.resp_valid.value:
            response_seen = True

    assert writeback_seen and response_seen


# ============================================================
# RUNNER
# ============================================================

def test_cache_controller2():
    sim = os.getenv("SIM", "icarus")

    proj_path = Path(__file__).resolve().parent.parent

    sources = [
        proj_path / "golden" / "cache_controller2.v",
    ]

    runner = get_runner(sim)

    runner.build(
        sources=sources,
        hdl_toplevel="cache_controller2",
        always=True,
    )

    runner.test(
        hdl_toplevel="cache_controller2",
        test_module="test_cache_controller2_hidden",
    )
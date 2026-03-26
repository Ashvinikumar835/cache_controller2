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

            # guarantee forward progress
            if stall % 4 == 0:
                dut.mem_ready.value = 1

                if dut.mem_req_rw.value == 0:
                    dut.mem_rdata.value = (
                        0xBEEF0000 | (int(dut.mem_addr.value) & 0xFFFF)
                    )

# ============================================================
# MAIN TEST
# ============================================================

@cocotb.test()
async def cache_controller_test(dut):

    # CLOCK
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start(start_high=False))

    # MEMORY MODEL
    cocotb.start_soon(memory_model(dut))

    # INIT
    dut.req_valid.value = 0
    dut.req_rw.value = 0
    dut.req_addr.value = 0
    dut.req_wdata.value = 0
    dut.mem_ready.value = 0
    dut.mem_rdata.value = 0

    # RESET
    await reset_dut(dut)

    # ============================================================
    # FORCE CACHE STATE
    # ============================================================
    dut.valid.value = 1
    dut.tag.value   = 0x00100
    dut.data.value  = 0xA5A5A5A5
    dut.dirty.value = 0

    await RisingEdge(dut.clk)

    # ---------------- TEST 1: READ HIT ----------------
    await send_request(dut, 0, (0x00100 << 12))
    data = await wait_for_response(dut)
    assert data == 0xA5A5A5A5, "READ HIT FAILED"

    # ---------------- TEST 2: WRITE HIT ----------------
    await send_request(dut, 1, (0x00100 << 12), 0xDEADBEEF)

    for _ in range(5):
        await RisingEdge(dut.clk)

    assert int(dut.data.value) == 0xDEADBEEF
    assert int(dut.dirty.value) == 1



    # ---------------- TEST 5: MULTIPLE WRITES ----------------
    await send_request(dut, 1, (0x00100 << 12), 0x11111111)
    await RisingEdge(dut.clk)

    await send_request(dut, 1, (0x00100 << 12), 0x22222222)

    for _ in range(3):
        await RisingEdge(dut.clk)

    assert int(dut.data.value) == 0x22222222

  
    # ---------------- TEST 7: CLEAN MISS ----------------
    dut.valid.value = 0
    dut.dirty.value = 0

    await send_request(dut, 0, 0x00002000)
    data = await wait_for_response(dut, 30)

    assert data is not None, "CLEAN MISS FAILED"

    # ---------------- TEST 8: DIRTY MISS ----------------
    dut.valid.value = 1
    dut.dirty.value = 1
    dut.tag.value   = 0x00100
    dut.data.value  = 0xAAAA5555

    await send_request(dut, 0, (0x00200 << 12))

    writeback_seen = False
    response_seen  = False

    for _ in range(30):
        await RisingEdge(dut.clk)

        if dut.mem_req_valid.value == 1 and dut.mem_req_rw.value == 1:
            writeback_seen = True

        if dut.resp_valid.value == 1:
            response_seen = True

    assert writeback_seen and response_seen, "DIRTY MISS FAILED"

    print("\nALL TESTS PASSED\n")


#########################
# ---------------- TEST 9: CLEAN MISS ----------------
    dut.valid.value = 0
    dut.dirty.value = 0

    await send_request(dut, 0, 0x00001000)
    data = await wait_for_response(dut, 30)

    assert data is not None, "CLEAN MISS2 FAILED"

    # ---------------- TEST 10: DIRTY MISS ----------------
    dut.valid.value = 1
    dut.dirty.value = 1
    dut.tag.value   = 0x00100
    dut.data.value  = 0xAAAA5555

    await send_request(dut, 0, (0x00200 << 10))

    writeback_seen = False
    response_seen  = False

    for _ in range(30):
        await RisingEdge(dut.clk)

        if dut.mem_req_valid.value == 1 and dut.mem_req_rw.value == 1:
            writeback_seen = True

        if dut.resp_valid.value == 1:
            response_seen = True

    assert writeback_seen and response_seen, "DIRTY MISS2 FAILED"

    print("\nALL TESTS PASSED\n")

#########################
# ---------------- TEST 9: CLEAN MISS ----------------
    dut.valid.value = 0
    dut.dirty.value = 0

    await send_request(dut, 0, 0x00010000)
    data = await wait_for_response(dut, 30)

    assert data is not None, "CLEAN MISS2 FAILED"

    # ---------------- TEST 10: DIRTY MISS ----------------
    dut.valid.value = 1
    dut.dirty.value = 1
    dut.tag.value   = 0x00100
    dut.data.value  = 0xAAAA5555

    await send_request(dut, 0, (0x00200 << 9))

    writeback_seen = False
    response_seen  = False

    for _ in range(30):
        await RisingEdge(dut.clk)

        if dut.mem_req_valid.value == 1 and dut.mem_req_rw.value == 1:
            writeback_seen = True

        if dut.resp_valid.value == 1:
            response_seen = True

    assert writeback_seen and response_seen, "DIRTY MISS2 FAILED"

    print("\nALL TESTS PASSED\n")


# ============================================================
# RUNNER (PYTEST ENTRY)
# ============================================================

def test_cache_controller2():
    """Pytest entry point for cocotb runner"""

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

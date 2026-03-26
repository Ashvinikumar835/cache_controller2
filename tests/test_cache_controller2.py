from __future__ import annotations

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb_tools.runner import get_runner


async def reset_dut(dut) -> None:
    dut.rst_n.value = 0
    dut.req_valid.value = 0
    dut.req_rw.value = 0
    dut.req_addr.value = 0
    dut.req_wdata.value = 0
    dut.mem_ready.value = 0
    dut.mem_rdata.value = 0

    for _ in range(5):
        await RisingEdge(dut.clk)

    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def send_read(dut, addr: int) -> None:
    dut.req_valid.value = 1
    dut.req_rw.value = 0
    dut.req_addr.value = addr
    await RisingEdge(dut.clk)
    dut.req_valid.value = 0


@cocotb.test()
async def read_hit_returns_cached_data(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start(start_high=False))
    await reset_dut(dut)

    # Force a valid cache line
    dut.valid.value = 1
    dut.dirty.value = 0
    dut.tag.value = 0x00100
    dut.data.value = 0xA5A5A5A5
    await RisingEdge(dut.clk)

    await send_read(dut, 0x00100 << 12)

    observed = None
    for _ in range(20):
        await RisingEdge(dut.clk)
        if int(dut.resp_valid.value) == 1:
            observed = int(dut.resp_rdata.value)
            break

    assert observed == 0xA5A5A5A5, "read hit did not return cached data"


def test_cache_controller2():
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    sources = [proj_path / "sources" / "cache_controller2.v"]

    runner = get_runner(sim)
    runner.build(sources=sources, hdl_toplevel="cache_controller2", always=True)
    runner.test(hdl_toplevel="cache_controller2", test_module="test_cache_controller2")

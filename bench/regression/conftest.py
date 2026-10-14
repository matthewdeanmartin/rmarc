"""Safety checks around pytest-benchmark's existing comparison machinery."""

import ctypes
import hashlib
import os
from pathlib import Path

import pytest


def _pin_to_one_cpu():
    """Keep one local pytest process off mixed fast/slow CPU cores."""
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.GetProcessAffinityMask.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        process = kernel.GetCurrentProcess()
        allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
        if not kernel.GetProcessAffinityMask(process, ctypes.byref(allowed), ctypes.byref(system)):
            raise ctypes.WinError(ctypes.get_last_error())
        mask = allowed.value & -allowed.value
        if not kernel.SetProcessAffinityMask(process, mask):
            raise ctypes.WinError(ctypes.get_last_error())
        return mask.bit_length() - 1
    if hasattr(os, "sched_getaffinity"):
        cpu = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {cpu})
        return cpu
    return None


def pytest_configure(config):
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise pytest.UsageError("Performance regression timings are local-only; do not run on GitHub Actions.")
    if config.getoption("numprocesses", default=0):
        raise pytest.UsageError("Run performance regression checks without xdist workers.")
    config._rmarc_perf_cpu = _pin_to_one_cpu()


def pytest_benchmark_update_machine_info(config, machine_info):
    fixture = Path(__file__).resolve().parents[2] / "test_pymarc/test.dat"
    machine_info["rmarc_fixture_sha256"] = hashlib.sha256(fixture.read_bytes()).hexdigest()
    machine_info["rmarc_workload_version"] = 1
    machine_info["rmarc_cpu"] = config._rmarc_perf_cpu


def pytest_benchmark_compare_machine_info(config, benchmarksession, machine_info, compared_benchmark):
    previous = compared_benchmark["machine_info"]
    # CPU frequency readings fluctuate. Require stable identity/workload fields.
    keys = (
        "node",
        "processor",
        "machine",
        "python_version",
        "python_implementation",
        "python_compiler",
        "system",
        "release",
        "rmarc_fixture_sha256",
        "rmarc_workload_version",
        "rmarc_cpu",
    )
    if any(machine_info.get(key) != previous.get(key) for key in keys):
        raise pytest.UsageError("Baseline machine, Python or fixture differs. Use a matching baseline.")

# SPDX-License-Identifier: Apache-2.0
"""Pure-Python archive/link/ROM checks: python3 emitter/selftest_build_mmp.py (no ARM tools)."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import build_mmp as B
from euser_def import DefMap
from mmp import Mmp


def self_test():
    spec = importlib.util.spec_from_file_location("rom_args", Path(B.REPO) / "kernel" / "rom_args.py")
    rom_args = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rom_args)
    with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
        root = Path(tmp)
        projects = {
            "user": Mmp(str(root / "user.mmp"), target="user.dll", targettype="dll",
                        staticlibs=["IMAGEPROCESSORPERF.LIB"]),
            "perf_key": Mmp(str(root / "perf.mmp"), target="ImageProcessorPerf.LIB", targettype="lib",
                            sources=[str(root / "one.cpp"), str(root / "two.cpp")], macros=["FROM_MMP"]),
        }
        registry = {k: {"mmp": m.path} for k, m in projects.items()}
        registry["user"]["rtti"] = True
        registry["perf_key"].update(defs=["FROM_REGISTRY"], flags=["-fexample"])
        commands, compiles = [], []

        def compile_one(src, obj, flags, env):
            compiles.append((src, flags, env))
            Path(obj).write_text(src)
            return src, 0, ""

        def run(args, **kw):
            if args[0] == B.BE.NM:   # the FP-register check (US3) lists each image's undefined symbols
                return type("Result", (), {"returncode": 0, "stdout": ""})()
            commands.append(args)
            if args[1] == "rcs":
                assert args[0] == "/sdk/bin/arm-none-eabi-ar"
                assert not Path(args[2]).exists()  # rebuild must discard removed members
                Path(args[2]).write_text("\n".join(args[3:]))
            else:
                assert args[0] == B.BE.GCC
                Path(args[args.index("-o") + 1]).write_bytes(b"ELF")
            return type("Result", (), {"returncode": 0, "stderr": ""})()

        for obj, name, value in [
            (B.C, "COMPONENTS", registry), (B, "OUT_ROOT", str(root / "work")),
            (B, "HERE", str(root / "emitter")), (B.BE, "GCC", "/sdk/bin/arm-none-eabi-gcc"),
            (B, "_compile_one", compile_one), (B.subprocess, "run", run), (B, "PARALLEL", 1),
        ]:
            stack.enter_context(patch.object(obj, name, value))
        stack.enter_context(patch.object(B.MMP, "parse", side_effect=lambda p: next(
            m for m in projects.values() if m.path == p)))
        B._component_mmp.cache_clear()
        stack.callback(B._component_mmp.cache_clear)
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

        # Only requested keys, with libraries first; resources retain the caller's order.
        for rsc, expected in [(False, ["perf_key", "user"]), (True, ["user", "perf_key"])]:
            with patch.object(sys, "argv", ["build_mmp", *(["--rsc"] if rsc else []), "user", "perf_key"]), \
                    patch.object(B, "build", return_value=0) as build:
                assert B.main() == 0
                assert build.call_args_list == [((k, rsc),) for k in expected]

        # Missing providers (even a DLL with the same TARGET), and unbuilt providers, are clear failures.
        for lib, message in [("user.lib", "no registered TARGETTYPE lib"),
                             ("missing.lib", "no registered TARGETTYPE lib"),
                             ("imageprocessorperf.lib", "build perf_key first")]:
            with patch.object(projects["user"], "staticlibs", [lib]):
                try:
                    B._static_archives(projects["user"])
                except RuntimeError as e:
                    assert lib in str(e) and message in str(e)
                else:
                    raise AssertionError("missing STATICLIBRARY accepted")

        # No .def, image runtime, or E32 emission for an archive; flags are still the normal project flags.
        with patch.object(Mmp, "def_path", side_effect=AssertionError("archive looked for .def")), \
                patch.object(B, "build_dll", side_effect=AssertionError("archive emitted E32")):
            assert B.build("perf_key") == 0
            archive = root / "work" / "perf_key" / "imageprocessorperf.a"
            assert archive.is_file()
            assert [s for s, _, _ in compiles] == projects["perf_key"].sources
            assert all({"-DFROM_MMP", "-DFROM_REGISTRY", "-fexample"} <= set(f) for _, f, _ in compiles)
            assert len(commands) == 1 and commands[0][1] == "rcs"
            projects["perf_key"].sources.pop()
            assert B.build("perf_key") == 0
            assert "two.cpp.o" not in archive.read_text()
        assert B._static_archives(projects["user"]) == [str(archive)]
        assert B.provider_maps(["perf_key.lib"]) == ({}, [])

        # Provider discovery tolerates an unrelated MMP missing from a partial checkout.
        component_mmp = B._component_mmp

        def partial_project(key):
            if key == "unavailable":
                raise FileNotFoundError("unfetched.mmp")
            return component_mmp(key)

        with patch.dict(registry, unavailable={"mmp": "unfetched.mmp"}), \
                patch.object(B, "_component_mmp", side_effect=partial_project):
            assert B._static_archives(projects["user"]) == [str(archive)]

        # --rsc must neither resolve nor build archives, including an image with a missing static provider.
        with patch.object(B, "_static_archives", side_effect=AssertionError("resources resolved archive")), \
                patch.object(B, "_compile_one", side_effect=AssertionError("resources compiled source")), \
                patch.object(B, "build_resources", return_value=0) as resources:
            assert B.build("user", True) == B.build("perf_key", True) == 0
            assert resources.call_count == 2

        # Run the real build control flow through BOTH links, stopping at ELF extraction.
        class Linked(Exception):
            pass

        def nm(kind, *paths):
            if kind == "--defined-only":
                assert str(archive) in paths   # exports supplied by archives must be rooted too
                return {"from_archive"}
            return set()

        with patch.object(Mmp, "def_path", return_value="test.def"), \
                patch.object(B, "parse_def", return_value=DefMap({1: "from_archive"}, 1)), \
                patch.object(B.BE, "_nm", side_effect=nm), \
                patch.object(B.BE, "_libgcc", return_value="libgcc.a"), \
                patch.object(B, "_libsupcxx", return_value="libsupc++.a"), \
                patch.object(B.devlink, "make_veneers", return_value="veneers.o"), \
                patch.object(B, "extract", side_effect=Linked):
            for _ in range(2):
                commands.clear()
                archive.write_text(archive.read_text() + "changed\n")
                try:
                    B.build("user")
                except Linked:
                    pass
                else:
                    raise AssertionError("did not reach ELF extraction")
                links = [c for c in commands if "-nostdlib" in c]
                assert len(links) == 2
                assert "-Wl,--unresolved-symbols=ignore-all" in links[0]
                assert "-Wl,--unresolved-symbols=ignore-all" not in links[1]
                for cmd in links:
                    start = cmd.index("-Wl,--start-group")
                    assert cmd[start:start + 5] == ["-Wl,--start-group", str(archive), "libsupc++.a",
                                                    "libgcc.a", "-Wl,--end-group"]
                assert "-Wl,-u,from_archive" in (root / "work" / "user" / "link.rsp").read_text()

        # A stale DLL/manifest and explicit ROM metadata must not smuggle a lib into the ROM.
        (root / "emitter").mkdir()
        for name in ("user.dll", "perf_key.dll", "perf_key.dll.romfiles"):
            (root / "emitter" / name).write_text("stale=data")
        registry["perf_key"]["rom_data"] = ["stale=data"]
        with patch.object(rom_args, "REPO", tmp), contextlib.redirect_stdout(io.StringIO()) as out:
            rom_args.main()
            assert out.getvalue().splitlines() == ["--xip", "Sys\\Bin\\user.dll=emitter/user.dll"]
    print("build_mmp self-test: OK")


if __name__ == "__main__":
    self_test()

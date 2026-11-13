// SPDX-License-Identifier: Apache-2.0
// The EHABI personality routines our unwind tables name. Each table entry carries an R_ARM_NONE dependency on
// __aeabi_unwind_cpp_pr0/1/2 that is never called; these weak placeholders keep the link from pulling libgcc's
// unwinder (and the C++ runtime it needs) into every image. The real routines are drtaeabi.dll's, which unwinds
// old RVCT binaries' TRAPs through our frames (emitter/build_mmp.py leaves this file out of it).
extern "C" __attribute__((weak)) void __aeabi_unwind_cpp_pr0() {}
extern "C" __attribute__((weak)) void __aeabi_unwind_cpp_pr1() {}
extern "C" __attribute__((weak)) void __aeabi_unwind_cpp_pr2() {}

// SPDX-License-Identifier: Apache-2.0
// toolchain/overlay/e32std.h -- include-path overlay in front of the real <e32std.h>.
//
// __ASSERT_ALWAYS_NO_LEAVE expands a TRAP by hand (TTrap _t; _t.Trap(_r)), which in code built with VFP doesn't keep
// d8-d15 across a leave (docs user-side-smp.md US3). Its leave path panics, so nothing reads them; routing it through
// NeoTrapFp like the TRAP macros (overlay e32cmn.h) keeps build_mmp's "VFP code calls TTrap::Trap" check exact.
#ifndef SYM_OVERLAY_E32STD_H
#define SYM_OVERLAY_E32STD_H
#include_next <e32std.h>

#if defined(NEO_TRAP_FP) && !defined(__LEAVE_EQUALS_THROW__)
#undef __ASSERT_ALWAYS_NO_LEAVE
#define __ASSERT_ALWAYS_NO_LEAVE(_s) \
	{ \
	TInt _r; \
	TNeoTrapFp _t; \
	if (NeoTrapFp(&_t.iTrap, _r) == 0) \
		{ \
		_s; \
		TTrap::UnTrap(); \
		} \
	else \
		User::PanicUnexpectedLeave(); \
	}
#endif

#endif

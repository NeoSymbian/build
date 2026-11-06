// SPDX-License-Identifier: Apache-2.0
// neo_glue.cpp -- NeoSymbian R0: the C++ half of a Symbian EXE whose logic is Rust (NeoSymbian/e32-rs, rust-hello).
// E32Main is here; the Rust staticlib provides rust_hello() and calls back neo_debug_print() to reach RDebug.
#include <e32std.h>
#include <e32debug.h>

extern "C" TInt rust_hello(TInt aA, TInt aB);

extern "C" void neo_debug_print(const TUint8* aPtr, TInt aLen)
	{
	TPtrC8 text(aPtr, aLen);
	RDebug::Printf("%S", &text);
	}

GLDEF_C TInt E32Main()
	{
	RDebug::Printf("neo: start");
	TInt r = rust_hello(6, 7);
	RDebug::Printf("neo: rust_hello(6, 7) = %d", r);
	return r == 42 ? KErrNone : KErrGeneral;
	}

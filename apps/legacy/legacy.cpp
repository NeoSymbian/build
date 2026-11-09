// SPDX-License-Identifier: Apache-2.0
// LEGACY.EXE -- runs a 2010 Symbian GUI program inside neoui (NeoSymbian P2, the "guest window server").
//
// neoui owns the display and the input, so the stock window server cannot. This neoui app:
//   1. makes the global chunk "NeoUiLegacy" with the display's own geometry (HAL size, stride, first-pixel offset);
//      the patched screen driver (graphics scnew.cpp) then draws into it, and the patched window server (WSTOP.CPP,
//      EVENT.CPP) runs as a guest: no display or event-hook ownership;
//   2. starts EWSRV.EXE -NoShell and then the program named on its command line (e.g. "grid");
//   3. shows the guest screen, scaled to fit, in its neoui surface, and turns neoui's taps and keys into raw events
//      for the guest window server (RWsSession::SimulateRawEvent).
// Back (claimed) or Quit ends the program, the guest window server and itself.

#include <e32base.h>
#include <e32debug.h>
#include <e32keys.h>
#include <hal.h>
#include <w32std.h>

namespace {

// --- the NeoUi protocol (neoui/crates/neoui-proto/src/ipc.rs) ---
_LIT(KNeoUi, "NeoUi");
const TInt KGeometry = 1, KSurface = 2, KDamage = 3, KNextEvent = 4, KNav = 6;
const TInt KNavBack = 1, KNavOptions = 2;
const TUint KTouch = 1, KKey = 2, KQuit = 3, KBack = 4, KOptions = 5, KVisible = 6;

class RNeoUi : public RSessionBase
	{
public:
	TInt Connect() { return CreateSession(KNeoUi, TVersion(1, 0, 0), 4); }
	TInt Geometry(TDes8& aOut) { return SendReceive(KGeometry, TIpcArgs(&aOut)); }
	TInt Surface() { return SendReceive(KSurface); }
	TInt Damage(TInt aX, TInt aY, TInt aW, TInt aH) { return SendReceive(KDamage, TIpcArgs(aX, aY, aW, aH)); }
	void NextEvent(TDes8& aOut, TRequestStatus& aStatus) { SendReceive(KNextEvent, TIpcArgs(&aOut), aStatus); }
	TInt Nav(TInt aClaims) { return SendReceive(KNav, TIpcArgs(aClaims)); }
	};

TUint Le32(const TDesC8& aB, TInt aI)
	{
	return aB[aI] | aB[aI + 1] << 8 | aB[aI + 2] << 16 | TUint(aB[aI + 3]) << 24;
	}

_LIT(KLegacyChunk, "NeoUiLegacy");
_LIT(KGuestWserv, "EWSRV.EXE");
_LIT(KNoShell, "-NoShell");
const TInt KFrameUs = 100000;	// shortcut: the whole frame copied 10 times a second; real damage via SubmitUpdate later

// The guest screen (HAL geometry) fitted into the surface: centred, aspect kept.
struct TFit
	{
	TInt iW, iH, iStride, iOffset;	// guest: pixels, bytes per line, bytes to the first pixel
	TInt iSw, iSh;					// surface
	TInt iDx, iDy, iDw, iDh;		// where the guest lands in the surface
	void Compute()
		{
		if (iSw * iH <= iSh * iW)
			{ iDw = iSw; iDh = iH * iSw / iW; }
		else
			{ iDh = iSh; iDw = iW * iSh / iH; }
		iDx = (iSw - iDw) / 2;
		iDy = (iSh - iDh) / 2;
		}
	TBool ToGuest(TInt aX, TInt aY, TInt& aGx, TInt& aGy) const
		{
		if (aX < iDx || aY < iDy || aX >= iDx + iDw || aY >= iDy + iDh)
			return EFalse;
		aGx = (aX - iDx) * iW / iDw;
		aGy = (aY - iDy) * iH / iDh;
		return ETrue;
		}
	};

void Blit(const TFit& aF, const TUint8* aGuest, TUint32* aSurface)
	{
	for (TInt y = 0; y < aF.iDh; ++y)
		{
		const TUint32* src = reinterpret_cast<const TUint32*>(aGuest + aF.iOffset + (y * aF.iH / aF.iDh) * aF.iStride);
		TUint32* dst = aSurface + (aF.iDy + y) * aF.iSw + aF.iDx;
		for (TInt x = 0; x < aF.iDw; ++x)
			dst[x] = 0xFF000000 | src[x * aF.iW / aF.iDw];	// guest EColor16MA -> XRGB
		}
	}

// neoui key codes (Unicode + Enter 13, Backspace 8, Esc 27, arrows 0xF807..0xF80A) -> standard scan codes
TInt ScanCode(TUint aCode)
	{
	switch (aCode)
		{
	case 13: return EStdKeyEnter;
	case 8: return EStdKeyBackspace;
	case 27: return EStdKeyEscape;
	case ' ': return EStdKeySpace;
	case EKeyLeftArrow: return EStdKeyLeftArrow;
	case EKeyRightArrow: return EStdKeyRightArrow;
	case EKeyUpArrow: return EStdKeyUpArrow;
	case EKeyDownArrow: return EStdKeyDownArrow;
	default: break;
		}
	if (aCode >= 'a' && aCode <= 'z')
		return aCode - 'a' + 'A';
	if ((aCode >= 'A' && aCode <= 'Z') || (aCode >= '0' && aCode <= '9'))
		return aCode;
	return 0;
	}

void Key(RWsSession& aWs, TInt aScan)
	{
	TRawEvent ev;
	ev.Set(TRawEvent::EKeyDown, aScan);
	aWs.SimulateRawEvent(ev);
	ev.Set(TRawEvent::EKeyUp, aScan);
	aWs.SimulateRawEvent(ev);
	aWs.Flush();
	}

TInt Run()
	{
	TBuf<64> program;
	User::CommandLine(program);
	program.Trim();
	if (!program.Length())
		program = _L("grid");

	RNeoUi ui;
	TInt err = ui.Connect();
	if (err)
		return err;
	TBuf8<12> geo;
	if ((err = ui.Geometry(geo)) != KErrNone)
		return err;
	RChunk surface;
	if ((err = surface.SetReturnedHandle(ui.Surface())) != KErrNone)
		return err;

	TFit f;
	f.iSw = Le32(geo, 0);
	f.iSh = Le32(geo, 4);
	TInt mode = 0;
	HAL::Get(HALData::EDisplayXPixels, f.iW);
	HAL::Get(HALData::EDisplayYPixels, f.iH);
	HAL::Get(HALData::EDisplayMode, mode);
	f.iStride = mode;		// HAL takes the mode in and gives the value back
	f.iOffset = mode;
	HAL::Get(HALData::EDisplayOffsetBetweenLines, f.iStride);
	HAL::Get(HALData::EDisplayOffsetToFirstPixel, f.iOffset);
	f.Compute();

	RChunk guest;
	const TInt size = f.iOffset + f.iStride * f.iH;
	if ((err = guest.CreateGlobal(KLegacyChunk, size, size)) != KErrNone)
		return err;
	Mem::FillZ(guest.Base(), size);
	Mem::FillZ(surface.Base(), f.iSw * f.iSh * 4);

	RProcess wserv;
	if ((err = wserv.Create(KGuestWserv, KNoShell)) != KErrNone)
		return err;
	wserv.Resume();
	RWsSession ws;
	for (TInt i = 0; (err = ws.Connect()) != KErrNone && i < 100; ++i)
		User::After(100000);
	if (err)
		{
		wserv.Kill(0);
		return err;
		}
	RDebug::Printf("legacy: guest wserv %dx%d up, surface %dx%d", f.iW, f.iH, f.iSw, f.iSh);

	RProcess app;
	if ((err = app.Create(program, KNullDesC)) != KErrNone)
		{
		RDebug::Printf("legacy: cannot start the program (%d)", err);
		wserv.Kill(0);
		return err;
		}
	app.Resume();
	ui.Nav(KNavBack | KNavOptions);

	TBuf8<16> ev;
	TRequestStatus evStatus, tick;
	RTimer timer;
	timer.CreateLocal();
	ui.NextEvent(ev, evStatus);
	timer.After(tick, KFrameUs);
	TBool visible = ETrue, running = ETrue;
	while (running)
		{
		User::WaitForRequest(evStatus, tick);
		if (tick != KRequestPending && evStatus != KRequestPending)
			User::WaitForAnyRequest();	// both completed: two signals, WaitForRequest took one
		if (tick != KRequestPending)
			{
			if (visible)
				{
				Blit(f, guest.Base(), reinterpret_cast<TUint32*>(surface.Base()));
				ui.Damage(f.iDx, f.iDy, f.iDw, f.iDh);
				}
			if (app.ExitType() != EExitPending)
				running = EFalse;	// the program ended by itself
			else
				timer.After(tick, KFrameUs);
			}
		if (evStatus == KRequestPending)
			continue;
		if (evStatus.Int() != KErrNone)
			break;
		const TUint kind = Le32(ev, 0), a = Le32(ev, 4), b = Le32(ev, 8), c = Le32(ev, 12);
		if (kind == KTouch)
			{
			TInt gx, gy;
			const TUint phase = a & 0xFF;
			if (f.ToGuest(b, c, gx, gy))
				{
				TRawEvent raw;
				raw.Set(phase == 0 ? TRawEvent::EButton1Down : phase == 2 ? TRawEvent::EButton1Up
					: TRawEvent::EPointerMove, gx, gy);
				ws.SimulateRawEvent(raw);
				ws.Flush();
				if (phase != 1)
					RDebug::Printf("legacy: raw %d %d %d", raw.Type(), gx, gy);
				}
			}
		else if (kind == KKey && a)
			{
			const TInt scan = ScanCode(b);
			if (scan)
				Key(ws, scan);
			}
		else if (kind == KOptions)
			Key(ws, EStdKeyDevice0);		// the left softkey (Options)
		else if (kind == KVisible)
			visible = a != 0;
		else if (kind == KQuit || kind == KBack)
			running = EFalse;
		if (running)
			ui.NextEvent(ev, evStatus);
		}

	RDebug::Printf("legacy: closing");
	if (tick == KRequestPending)
		{
		timer.Cancel();
		User::WaitForRequest(tick);
		}
	timer.Close();
	if (app.ExitType() == EExitPending)
		app.Kill(0);
	app.Close();
	ws.Close();
	wserv.Kill(0);
	wserv.Close();
	guest.Close();
	surface.Close();
	ui.Close();		// an outstanding NEXT_EVENT ends with the process, as for neoui's own apps
	return KErrNone;
	}

} // namespace

GLDEF_C TInt E32Main()
	{
	CTrapCleanup* cleanup = CTrapCleanup::New();
	const TInt err = cleanup ? Run() : KErrNoMemory;
	delete cleanup;
	return err;
	}

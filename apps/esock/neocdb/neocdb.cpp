// SPDX-License-Identifier: Apache-2.0
// NEOCDB.EXE -- CommsDat for ESOCK over NeoNet (docs hardware/wifi.md W5a). The ROM's CommsDat repository is the 2010 empty one
// (policies only); at boot (NEONET.EXE starts this) the records are written through the CommsDat API itself, so they
// always match this CommsDat's schema:
//   MCPR (neotier's), CPR and SCPR (the core vanilla ones), the transport flow shim (Protocol);
//   access point 10000 "NeoNet" with those; tier 2048 (KAfInet: implicit sockets and resolvers) with neotier's tier
//   manager, running in ESock_IP, its default access point 10000; GlobalSettings' default tier = 2048;
//   the link layer under it (browser WB2d): tier 0x0E00400D with neotier's link tier manager, access point 10001
//   "NeoNetLink" whose flow is neotier's link flow, and access point 10000's next layer = 10001 (custom selection
//   policy: the access point's tag, read by the MCPR's simple selection).
// Each part is done once: the database persists on C:, and one set up before the link layer gains it here.
// Prints "neocdb: ..." lines.
#include <e32base.h>
#include <e32debug.h>
#include <commsdattypesv1_1.h>
#include <commsdattypesv1_1_partner.h>
#include <commsdattypeinfov1_1_internal.h>

using namespace CommsDat;

const TUint KTierTag = 2048;							// KAfInet
const TUint KApTag = 10000;
const TUint KTierManagerUid = 0x0E004005;				// neotier.dll
const TUint KMCprUid = 0x0E004006;						// neotier.dll
const TUint KCprUid = 0x102822F3;						// coreprovidersecom: vanilla CPR
const TUint KSCprUid = 0x102822F4;						// coreprovidersecom: vanilla SCPR
const TUint KFlowShimUid = 0x101F7482;					// esocksvr: the transport flow shim
const TUint KLinkTierTag = 0x0E00400D;					// the link tier (private)
const TUint KLinkApTag = 10001;
const TUint KLinkTierManagerUid = 0x0E00400B;			// neotier.dll
const TUint KLinkFlowUid = 0x0E00400C;					// neotier.dll: the link flow's factory

template <class T> static T* NewRecordLC(TMDBElementId aType)
	{
	T* r = static_cast<T*>(CCDRecordBase::RecordFactoryL(aType));
	CleanupStack::PushL(r);
	return r;
	}

static void SetName(CCDRecordBase& aRec, const TDesC& aName)
	{
	aRec.iRecordName.SetMaxLengthL(aName.Length());
	aRec.iRecordName = aName;
	}

static void SetText(CMDBField<TDesC>& aField, const TDesC& aText)
	{
	aField.SetMaxLengthL(aText.Length());
	aField = aText;
	}

// store aRec as a new record: its table and record id, for links
static TMDBElementId StoreL(CMDBSession& aDb, CCDRecordBase& aRec)
	{
	aRec.SetRecordId(KCDNewRecordRequest);
	aRec.StoreL(aDb);
	return aRec.ElementId() & (KCDMaskShowRecordType | KCDMaskShowRecordId);
	}

static TMDBElementId UidRecordL(CMDBSession& aDb, TMDBElementId aType, const TDesC& aName, TUint aUid)
	{
	CCDRecordBase* r = NewRecordLC<CCDRecordBase>(aType);
	SetName(*r, aName);
	switch (aType)
		{
	case KCDTIdMCprRecord: static_cast<CCDMCprRecord*>(r)->iMCprUid = aUid; break;
	case KCDTIdCprRecord: static_cast<CCDCprRecord*>(r)->iCprUid = aUid; break;
	case KCDTIdSCprRecord: static_cast<CCDSCprRecord*>(r)->iSCprUid = aUid; break;
	default: static_cast<CCDProtocolRecord*>(r)->iProtocolUid = aUid; break;
		}
	TMDBElementId id = StoreL(aDb, *r);
	CleanupStack::PopAndDestroy(r);
	return id;
	}

static TBool TierPresentL(CMDBSession& aDb, TUint aTag)
	{
	CCDTierRecord* tier = NewRecordLC<CCDTierRecord>(KCDTIdTierRecord);
	tier->iRecordTag = aTag;
	TBool found = tier->FindL(aDb);
	CleanupStack::PopAndDestroy(tier);
	return found;
	}

// a tier with neotier's tier manager aTmUid, and its default access point aApTag with the given providers and flow
static TMDBElementId TierAndApL(CMDBSession& aDb, TUint aTierTag, TUint aTmUid, const TDesC& aTierName,
	const TDesC& aTmName, TUint aApTag, const TDesC& aApName, TMDBElementId aMCpr, TMDBElementId aCpr,
	TMDBElementId aSCpr, TMDBElementId aFlow, TInt aNextApTag)
	{
	CCDTierRecord* tier = NewRecordLC<CCDTierRecord>(KCDTIdTierRecord);
	SetName(*tier, aTierName);
	tier->iRecordTag = aTierTag;
	tier->iTierImplUid = aTmUid;
	SetText(tier->iTierThreadName, _L("ESock_IP"));
	SetText(tier->iTierManagerName, aTmName);
	tier->iPromptUser = EFalse;
	TMDBElementId tierId = StoreL(aDb, *tier);

	CCDAccessPointRecord* ap = NewRecordLC<CCDAccessPointRecord>(KCDTIdAccessPointRecord);
	SetName(*ap, aApName);
	ap->iRecordTag = aApTag;
	ap->iTier = tierId;
	ap->iMCpr = aMCpr;
	ap->iCpr = aCpr;
	ap->iSCpr = aSCpr;
	ap->iProtocol = aFlow;
	ap->iCustomSelectionPolicy = aNextApTag;
	TMDBElementId apId = StoreL(aDb, *ap);
	CleanupStack::PopAndDestroy(ap);

	tier->iDefaultAccessPoint = apId;
	tier->ModifyL(aDb);
	CleanupStack::PopAndDestroy(tier);
	return tierId;
	}

// tier 2048 and access point 10000, over the link layer
static void SetUpInetL(CMDBSession& aDb)
	{
	TMDBElementId mcpr = UidRecordL(aDb, KCDTIdMCprRecord, _L("neonetmcpr"), KMCprUid);
	TMDBElementId cpr = UidRecordL(aDb, KCDTIdCprRecord, _L("vanillacpr"), KCprUid);
	TMDBElementId scpr = UidRecordL(aDb, KCDTIdSCprRecord, _L("vanillascpr"), KSCprUid);
	TMDBElementId shim = UidRecordL(aDb, KCDTIdProtocolRecord, _L("sapshim"), KFlowShimUid);
	TMDBElementId tierId = TierAndApL(aDb, KTierTag, KTierManagerUid, _L("NeoNetTier"), _L("NeoNetTierManager"),
		KApTag, _L("NeoNet"), mcpr, cpr, scpr, shim, KLinkApTag);

	CCDGlobalSettingsRecord* gs = NewRecordLC<CCDGlobalSettingsRecord>(KCDTIdGlobalSettingsRecord);
	gs->SetRecordId(1);
	TRAPD(r, gs->LoadL(aDb));
	gs->iDefaultTier = tierId;
	if (r == KErrNone)
		gs->ModifyL(aDb);
	else
		{
		SetName(*gs, _L("Global settings"));
		gs->StoreL(aDb);
		}
	CleanupStack::PopAndDestroy(gs);
	RDebug::Printf("neocdb: CommsDat set up: tier 2048, access point %d", KApTag);
	}

// the link tier and access point 10001; an access point 10000 from before the link layer gets it as its next layer
static void SetUpLinkL(CMDBSession& aDb, TBool aOldInet)
	{
	TMDBElementId mcpr = UidRecordL(aDb, KCDTIdMCprRecord, _L("neonetlinkmcpr"), KMCprUid);
	TMDBElementId cpr = UidRecordL(aDb, KCDTIdCprRecord, _L("vanillalinkcpr"), KCprUid);
	TMDBElementId scpr = UidRecordL(aDb, KCDTIdSCprRecord, _L("vanillalinkscpr"), KSCprUid);
	TMDBElementId flow = UidRecordL(aDb, KCDTIdProtocolRecord, _L("neonetlinkflow"), KLinkFlowUid);
	TierAndApL(aDb, KLinkTierTag, KLinkTierManagerUid, _L("NeoNetLinkTier"), _L("NeoNetLinkTierManager"), KLinkApTag,
		_L("NeoNetLink"), mcpr, cpr, scpr, flow, 0);					// 0: the bottom, no next layer
	if (aOldInet)
		{
		CCDAccessPointRecord* ap = NewRecordLC<CCDAccessPointRecord>(KCDTIdAccessPointRecord);
		ap->iRecordTag = KApTag;
		if (!ap->FindL(aDb))
			User::Leave(KErrNotFound);
		ap->iCustomSelectionPolicy = KLinkApTag;
		ap->ModifyL(aDb);
		CleanupStack::PopAndDestroy(ap);
		}
	RDebug::Printf("neocdb: link layer set up: tier %08x, access point %d%s", KLinkTierTag, KLinkApTag,
		aOldInet ? " (access point 10000 now over it)" : "");
	}

static void SetUpL()
	{
	CMDBSession* db = CMDBSession::NewLC(KCDVersion1_2);
	TBool inet = TierPresentL(*db, KTierTag);
	TBool link = TierPresentL(*db, KLinkTierTag);
	if (inet && link)
		{
		RDebug::Printf("neocdb: tier 2048 and the link tier present: nothing to do");
		CleanupStack::PopAndDestroy(db);
		return;
		}
	db->OpenTransactionL();
	if (!link)
		SetUpLinkL(*db, inet);
	if (!inet)
		SetUpInetL(*db);
	db->CommitTransactionL();
	CleanupStack::PopAndDestroy(db);
	}

GLDEF_C TInt E32Main()
	{
	CTrapCleanup* cleanup = CTrapCleanup::New();
	if (!cleanup)
		return KErrNoMemory;
	TRAPD(r, SetUpL());
	if (r != KErrNone)
		RDebug::Printf("neocdb: CommsDat set-up failed (%d)", r);
	delete cleanup;
	return r;
	}

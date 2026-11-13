// SPDX-License-Identifier: Apache-2.0
// NEOCDB.EXE -- CommsDat for ESOCK over NeoNet (docs wifi.md W5a). The ROM's CommsDat repository is the 2010 empty one
// (policies only); at boot (NEONET.EXE starts this) the records are written through the CommsDat API itself, so they
// always match this CommsDat's schema:
//   MCPR (neotier's), CPR and SCPR (the core vanilla ones), the transport flow shim (Protocol);
//   access point 10000 "NeoNet" with those; tier 2048 (KAfInet: implicit sockets and resolvers) with neotier's tier
//   manager, running in ESock_IP, its default access point 10000; GlobalSettings' default tier = 2048.
// Done once: an existing tier 2048 means the database is set up (it persists on C:). Prints "neocdb: ..." lines.
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

static void SetUpL()
	{
	CMDBSession* db = CMDBSession::NewLC(KCDVersion1_2);
	CCDTierRecord* tier = NewRecordLC<CCDTierRecord>(KCDTIdTierRecord);
	tier->iRecordTag = KTierTag;
	if (tier->FindL(*db))
		{
		RDebug::Printf("neocdb: tier 2048 present (tier manager %08x): nothing to do", (TUint)tier->iTierImplUid);
		CleanupStack::PopAndDestroy(2, db);
		return;
		}
	db->OpenTransactionL();
	TMDBElementId mcpr = UidRecordL(*db, KCDTIdMCprRecord, _L("neonetmcpr"), KMCprUid);
	TMDBElementId cpr = UidRecordL(*db, KCDTIdCprRecord, _L("vanillacpr"), KCprUid);
	TMDBElementId scpr = UidRecordL(*db, KCDTIdSCprRecord, _L("vanillascpr"), KSCprUid);
	TMDBElementId shim = UidRecordL(*db, KCDTIdProtocolRecord, _L("sapshim"), KFlowShimUid);

	SetName(*tier, _L("NeoNetTier"));
	tier->iRecordTag = KTierTag;
	tier->iTierImplUid = KTierManagerUid;
	SetText(tier->iTierThreadName, _L("ESock_IP"));
	SetText(tier->iTierManagerName, _L("NeoNetTierManager"));
	tier->iPromptUser = EFalse;
	TMDBElementId tierId = StoreL(*db, *tier);

	CCDAccessPointRecord* ap = NewRecordLC<CCDAccessPointRecord>(KCDTIdAccessPointRecord);
	SetName(*ap, _L("NeoNet"));
	ap->iRecordTag = KApTag;
	ap->iTier = tierId;
	ap->iMCpr = mcpr;
	ap->iCpr = cpr;
	ap->iSCpr = scpr;
	ap->iProtocol = shim;
	TMDBElementId apId = StoreL(*db, *ap);
	CleanupStack::PopAndDestroy(ap);

	tier->iDefaultAccessPoint = apId;
	tier->ModifyL(*db);

	CCDGlobalSettingsRecord* gs = NewRecordLC<CCDGlobalSettingsRecord>(KCDTIdGlobalSettingsRecord);
	gs->SetRecordId(1);
	TRAPD(r, gs->LoadL(*db));
	gs->iDefaultTier = tierId;
	if (r == KErrNone)
		gs->ModifyL(*db);
	else
		{
		SetName(*gs, _L("Global settings"));
		gs->StoreL(*db);
		}
	CleanupStack::PopAndDestroy(gs);
	db->CommitTransactionL();
	RDebug::Printf("neocdb: CommsDat set up: tier %08x, access point %08x", tierId, apId);
	CleanupStack::PopAndDestroy(2, db);
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

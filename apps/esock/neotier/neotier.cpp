// SPDX-License-Identifier: Apache-2.0
// neotier.cpp -- NEOTIER.DLL (ECom), the always-up connection stack under ESOCK for NeoNet (docs wifi.md W5a): tier
// 2048 (KAfInet) gets our tier manager, whose selector always picks the tier's default access point, whatever the
// preferences (an IAP, a SNAP, none); the access point's MCPR is ours too, the core MCPR with nothing below it. The
// core vanilla CPR and SCPR (coreprovidersecom) and the transport flow shim (esocksvr) complete the stack; sockets
// reach neonet.prt through the shim. RConnection::Start runs start -> no bearer -> no next layer -> started.
// Built on the Symbian^3 core providers' public classes (CCoreTierManager, ASimpleSelectorBase,
// CCoreMetaConnectionProvider), as commsfw's loopback reference provider and dummypr do.
#include <ecom/implementationproxy.h>
#include <comms-infras/ss_log.h>
#include <comms-infras/coretiermanager.h>
#include <comms-infras/coretiermanageractivities.h>
#include <comms-infras/coremcpr.h>
#include <comms-infras/coremcpractivities.h>
#include <comms-infras/ss_tiermanager.h>
#include <comms-infras/ss_metaconnprov.h>
#include <comms-infras/ss_tiermanagerutils.h>
#include <comms-infras/simpleselectorbase.h>
#include <commsdattypesv1_1.h>
#include <commsdattypesv1_1_partner.h>
#include <in_sock.h>

using namespace ESock;
using namespace CommsDat;
using namespace MeshMachine;
using namespace Messages;

const TUint KNeoTierManagerUid = 0x0E004005;	// CommsDat TierImplUid (a signed field: below 0x80000000)
const TUint KNeoMCprUid = 0x0E004006;			// CommsDat MCprUid

// ---- the selector: the tier's default access point, always
class CNeoSelector : public CBase, public ASimpleSelectorBase
	{
public:
	explicit CNeoSelector(const Meta::SMetaData& aPrefs) : ASimpleSelectorBase(aPrefs) {}
private:
	virtual void SelectL(ISelectionNotify& aSelectionNotify)
		{
		if (!iDbs)
			iDbs = CMDBSession::NewL(KCDVersion1_2);
		if (!iTierRecord)
			iTierRecord = TierManagerUtils::LoadTierRecordL(TUid::Uid(KAfInet), *iDbs);
		TUint ap = iTierRecord->iDefaultAccessPoint;			// resolved to the access point's tag by the load
		User::LeaveIfError(ap ? KErrNone : KErrNotFound);
		aSelectionNotify.SelectComplete(this, FindOrCreateProviderL(ap));
		aSelectionNotify.SelectComplete(this, NULL);			// the last one
		}
	};

// ---- the tier manager
class CNeoTierManager : public CCoreTierManager
	{
public:
	static CNeoTierManager* NewL(CTierManagerFactoryBase& aFactory)
		{
		return new (ELeave) CNeoTierManager(aFactory);
		}
protected:
	explicit CNeoTierManager(CTierManagerFactoryBase& aFactory)
	:	CCoreTierManager(aFactory, TMActivities::coreTMActivities::Self())
		{
		}
	virtual MProviderSelector* DoCreateProviderSelectorL(const Meta::SMetaData& aPrefs)
		{
		return new (ELeave) CNeoSelector(aPrefs);
		}
	virtual void ReceivedL(const TRuntimeCtxId& aSender, const TNodeId& aRecipient, TSignatureBase& aMessage)
		{
		TNodeContext<CNeoTierManager> ctx(*this, aMessage, aSender, aRecipient);
		CCoreTierManager::Received(ctx);
		User::LeaveIfError(ctx.iReturn);
		}
	};

class CNeoTierManagerFactory : public CTierManagerFactoryBase
	{
public:
	static CNeoTierManagerFactory* NewL(TAny* aParentContainer)
		{
		return new (ELeave) CNeoTierManagerFactory(*reinterpret_cast<CTierManagerFactoryContainer*>(aParentContainer));
		}
protected:
	explicit CNeoTierManagerFactory(CTierManagerFactoryContainer& aParent)
	:	CTierManagerFactoryBase(TUid::Uid(KNeoTierManagerUid), TUid::Uid(KNeoTierManagerUid), aParent)
		{
		}
	virtual ACommsFactoryNodeId* DoCreateObjectL(TFactoryQueryBase& /*aQuery*/)
		{
		return CNeoTierManager::NewL(*this);
		}
	};

// ---- the MCPR: the core one, the bottom of the stack (no next layer to select)
class CNeoMCpr : public CCoreMetaConnectionProvider
	{
public:
	static CNeoMCpr* NewL(CMetaConnectionProviderFactoryBase& aFactory, const TProviderInfo& aInfo)
		{
		CNeoMCpr* self = new (ELeave) CNeoMCpr(aFactory, aInfo);
		CleanupStack::PushL(self);
		self->ConstructL();								// the access point's config from CommsDat (layer, selection)
		CleanupStack::Pop(self);
		return self;
		}
protected:
	CNeoMCpr(CMetaConnectionProviderFactoryBase& aFactory, const TProviderInfo& aInfo)
	:	CCoreMetaConnectionProvider(aFactory, aInfo, MCprActivities::coreMCprActivities::Self())
		{
		}
	virtual void ReceivedL(const TRuntimeCtxId& aSender, const TNodeId& aRecipient, TSignatureBase& aMessage)
		{
		TNodeContext<CNeoMCpr> ctx(*this, aMessage, aSender, aRecipient);
		CCoreMetaConnectionProvider::Received(ctx);
		User::LeaveIfError(ctx.iReturn);
		}
	};

class CNeoMCprFactory : public CMetaConnectionProviderFactoryBase
	{
public:
	static CNeoMCprFactory* NewL(TAny* aParentContainer)
		{
		return new (ELeave) CNeoMCprFactory(*reinterpret_cast<CMetaConnectionFactoryContainer*>(aParentContainer));
		}
protected:
	explicit CNeoMCprFactory(CMetaConnectionFactoryContainer& aParent)
	:	CMetaConnectionProviderFactoryBase(TUid::Uid(KNeoMCprUid), aParent)
		{
		}
	virtual ACommsFactoryNodeId* DoCreateObjectL(TFactoryQueryBase& aQuery)
		{
		const TMetaConnectionFactoryQuery& query = static_cast<const TMetaConnectionFactoryQuery&>(aQuery);
		return CNeoMCpr::NewL(*this, query.iProviderInfo);
		}
	};

const TImplementationProxy ImplementationTable[] =
	{
	IMPLEMENTATION_PROXY_ENTRY(KNeoTierManagerUid, CNeoTierManagerFactory::NewL),
	IMPLEMENTATION_PROXY_ENTRY(KNeoMCprUid, CNeoMCprFactory::NewL),
	};

EXPORT_C const TImplementationProxy* ImplementationGroupProxy(TInt& aTableCount)
	{
	aTableCount = sizeof(ImplementationTable) / sizeof(TImplementationProxy);
	return ImplementationTable;
	}

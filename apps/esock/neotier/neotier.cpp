// SPDX-License-Identifier: Apache-2.0
// neotier.cpp -- NEOTIER.DLL (ECom), the always-up connection stack under ESOCK for NeoNet (docs hardware/wifi.md W5a): tier
// 2048 (KAfInet) gets our tier manager, whose selector always picks the tier's default access point, whatever the
// preferences (an IAP, a SNAP, none); the access point's MCPR is ours too, the core MCPR with nothing below it. The
// core vanilla CPR and SCPR (coreprovidersecom) and the transport flow shim (esocksvr) complete the stack; sockets
// reach neonet.prt through the shim. RConnection::Start runs start -> no bearer -> no next layer -> started.
// Built on the Symbian^3 core providers' public classes (CCoreTierManager, ASimpleSelectorBase,
// CCoreMetaConnectionProvider), as commsfw's loopback reference provider and dummypr do.
// Under it, a link layer (browser WB2d): its own tier and access point (NEOCDB) whose flow, CNeoLinkFlow, carries no
// data and only answers the shim's connection-info query. A socket opened on an RConnection (P.I.P.S. opens every
// socket so) asks for a bearer at Bind/Connect (TNoBearer) and waits for a flow below it; without one it waited
// forever. Implicit sockets never ask, which is why they always worked.
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
#include <comms-infras/ss_subconnflow.h>
#include <comms-infras/es_protbinder.h>
#include <comms-infras/ss_flowbinders_internal.h>
#include <comms-infras/ss_nodemessages.h>
#include <comms-infras/ss_nodemessages_dataclient.h>
#include <es_prot_internal.h>
#include <in_sock.h>

using namespace ESock;
using namespace CommsDat;
using namespace MeshMachine;
using namespace Messages;

const TUint KNeoTierManagerUid = 0x0E004005;	// CommsDat TierImplUid (a signed field: below 0x80000000)
const TUint KNeoMCprUid = 0x0E004006;			// CommsDat MCprUid
const TUint KNeoLinkTierManagerUid = 0x0E00400B;	// the link tier's manager (CommsDat TierImplUid)
const TUint KNeoLinkFlowUid = 0x0E00400C;		// the link flow's factory (CommsDat ProtocolUid)
const TUint KNeoLinkTier = 0x0E00400D;			// the link tier's tag (NEOCDB)

// ---- the selector: the tier's default access point, always
class CNeoSelector : public CBase, public ASimpleSelectorBase
	{
public:
	CNeoSelector(const Meta::SMetaData& aPrefs, TUint aTier) : ASimpleSelectorBase(aPrefs), iTier(aTier) {}
private:
	virtual void SelectL(ISelectionNotify& aSelectionNotify)
		{
		if (!iDbs)
			iDbs = CMDBSession::NewL(KCDVersion1_2);
		if (!iTierRecord)
			iTierRecord = TierManagerUtils::LoadTierRecordL(TUid::Uid(iTier), *iDbs);
		TUint ap = iTierRecord->iDefaultAccessPoint;			// resolved to the access point's tag by the load
		User::LeaveIfError(ap ? KErrNone : KErrNotFound);
		aSelectionNotify.SelectComplete(this, FindOrCreateProviderL(ap));
		aSelectionNotify.SelectComplete(this, NULL);			// the last one
		}
	TUint iTier;
	};

// ---- the tier manager
class CNeoTierManager : public CCoreTierManager
	{
public:
	static CNeoTierManager* NewL(CTierManagerFactoryBase& aFactory, TUint aTier)
		{
		return new (ELeave) CNeoTierManager(aFactory, aTier);
		}
protected:
	CNeoTierManager(CTierManagerFactoryBase& aFactory, TUint aTier)
	:	CCoreTierManager(aFactory, TMActivities::coreTMActivities::Self()), iTier(aTier)
		{
		}
	virtual MProviderSelector* DoCreateProviderSelectorL(const Meta::SMetaData& aPrefs)
		{
		return new (ELeave) CNeoSelector(aPrefs, iTier);
		}
	virtual void ReceivedL(const TRuntimeCtxId& aSender, const TNodeId& aRecipient, TSignatureBase& aMessage)
		{
		TNodeContext<CNeoTierManager> ctx(*this, aMessage, aSender, aRecipient);
		CCoreTierManager::Received(ctx);
		User::LeaveIfError(ctx.iReturn);
		}
	TUint iTier;											// the tier whose default access point it selects
	};

// one factory per tier: tier 2048 (KAfInet) and the link tier under it
class CNeoTierManagerFactory : public CTierManagerFactoryBase
	{
public:
	static CNeoTierManagerFactory* NewL(TAny* aParentContainer)
		{
		return new (ELeave) CNeoTierManagerFactory(KNeoTierManagerUid, KAfInet,
			*reinterpret_cast<CTierManagerFactoryContainer*>(aParentContainer));
		}
	static CNeoTierManagerFactory* NewLinkL(TAny* aParentContainer)
		{
		return new (ELeave) CNeoTierManagerFactory(KNeoLinkTierManagerUid, KNeoLinkTier,
			*reinterpret_cast<CTierManagerFactoryContainer*>(aParentContainer));
		}
protected:
	CNeoTierManagerFactory(TUint aUid, TUint aTier, CTierManagerFactoryContainer& aParent)
	:	CTierManagerFactoryBase(TUid::Uid(aUid), TUid::Uid(aUid), aParent), iTier(aTier)
		{
		}
	virtual ACommsFactoryNodeId* DoCreateObjectL(TFactoryQueryBase& /*aQuery*/)
		{
		return CNeoTierManager::NewL(*this, iTier);
		}
	TUint iTier;
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

// ---- the link flow: the bottom of the stack, under the transport flow shim. No data passes here (NEONET.PRT talks
// to NEONET itself); it binds under the shim and answers its connection-info query, which is what a socket opened
// on an RConnection waits for (CTransportFlowShim::LockToConnectionInfo).
const TUint32 KNeoIapId = 1;							// shortcut: one interface, no IAP records; real ids with IAPs
const TUint32 KNeoNetId = 1;

class CNeoLinkFlow : public CSubConnectionFlowBase, public MFlowBinderControl, public MLowerControl
	{
public:
	CNeoLinkFlow(CSubConnectionFlowFactoryBase& aFactory, const TNodeId& aSubConn, CProtocolIntfBase* aProtocolIntf)
	:	CSubConnectionFlowBase(aFactory, aSubConn, aProtocolIntf)
		{
		}
	// MFlowBinderControl: the shim binds with no callbacks and ignores the sender returned
	virtual MLowerControl* GetControlL(const TDesC8& /*aProtocol*/)
		{
		return this;
		}
	virtual MLowerDataSender* BindL(const TDesC8& /*aProtocol*/, MUpperDataReceiver* /*aReceiver*/,
		MUpperControl* /*aControl*/)
		{
		if (iBinds++ == 0)
			iSubConnectionProvider.PostMessage(Id(), TCFControlProvider::TActive().CRef());
		return NULL;
		}
	virtual void Unbind(MUpperDataReceiver* /*aReceiver*/, MUpperControl* /*aControl*/)
		{
		if (iBinds > 0 && --iBinds == 0)
			{
			if (iDestroyPending)
				DeleteThisFlow();						// the last shim is gone: the TDestroy that came meanwhile
			else
				iSubConnectionProvider.PostMessage(Id(), TCFControlProvider::TIdle().CRef());
			}
		}
	virtual CSubConnectionFlowBase* Flow()
		{
		return this;
		}
	// MLowerControl: the connection info, as a TConnectionInfo package (sockets pass one, resolvers an empty buffer)
	virtual TInt Control(TUint aLevel, TUint aName, TDes8& aOption)
		{
		if (aLevel != KSOLProvider || aName != static_cast<TUint>(KSoConnectionInfo))
			return KErrNotSupported;
		TConnectionInfo info(KNeoIapId, KNeoNetId);
		TPckgC<TConnectionInfo> pkg(info);
		if (aOption.MaxLength() < pkg.Length())
			return KErrOverflow;
		aOption.Copy(pkg);
		return KErrNone;
		}
protected:
	virtual MFlowBinderControl* DoGetBinderControlL()
		{
		return this;
		}
	virtual void ReceivedL(const TRuntimeCtxId& aSender, const TNodeId& aRecipient, TSignatureBase& aMessage)
		{
		CSubConnectionFlowBase::ReceivedL(aSender, aRecipient, aMessage);
		if (aMessage.IsMessage<TEChild::TDestroy>())
			{
			// the SCPR (ESock_IP) can decide on an earlier TIdle while a shim binds here (ESock_DIP), on another
			// CPU: the shims hold raw pointers to this flow, so it lives until the last one unbinds
			if (iBinds > 0)
				iDestroyPending = ETrue;
			else
				DeleteThisFlow();
			}
		else if (aMessage.IsMessage<TCFDataClient::TStart>())
			iLastRequestOriginator.ReplyTo(Id(), TCFDataClient::TStarted().CRef());
		else if (aMessage.IsMessage<TCFDataClient::TStop>())
			iLastRequestOriginator.ReplyTo(Id(),
				TCFDataClient::TStopped(message_cast<TCFDataClient::TStop>(aMessage).iValue).CRef());
		else if (aMessage.IsMessage<TCFDataClient::TBindTo>())
			{
			// the bottom: nothing to bind to below
			User::LeaveIfError(message_cast<TCFDataClient::TBindTo>(aMessage).iNodeId.IsNull() ? KErrNone : KErrNotSupported);
			RClientInterface::OpenPostMessageClose(Id(), aSender, TCFDataClient::TBindToComplete().CRef());
			}
		// TProvisionConfig, TCommitBindTo, TError: nothing to keep or do
		}
private:
	TInt iBinds;
	TBool iDestroyPending;
	};

class CNeoLinkFlowFactory : public CSubConnectionFlowFactoryBase
	{
public:
	static CNeoLinkFlowFactory* NewL(TAny* aParentContainer)
		{
		return new (ELeave) CNeoLinkFlowFactory(*reinterpret_cast<CSubConnectionFlowFactoryContainer*>(aParentContainer));
		}
protected:
	explicit CNeoLinkFlowFactory(CSubConnectionFlowFactoryContainer& aParent)
	:	CSubConnectionFlowFactoryBase(TUid::Uid(KNeoLinkFlowUid), aParent)
		{
		}
	virtual CSubConnectionFlowBase* DoCreateFlowL(CProtocolIntfBase* aProtocolIntf, TFactoryQueryBase& aQuery)
		{
		const TDefaultFlowFactoryQuery& query = static_cast<const TDefaultFlowFactoryQuery&>(aQuery);
		return new (ELeave) CNeoLinkFlow(*this, query.iSCprId, aProtocolIntf);
		}
	};

const TImplementationProxy ImplementationTable[] =
	{
	IMPLEMENTATION_PROXY_ENTRY(KNeoTierManagerUid, CNeoTierManagerFactory::NewL),
	IMPLEMENTATION_PROXY_ENTRY(KNeoMCprUid, CNeoMCprFactory::NewL),
	IMPLEMENTATION_PROXY_ENTRY(KNeoLinkTierManagerUid, CNeoTierManagerFactory::NewLinkL),
	IMPLEMENTATION_PROXY_ENTRY(KNeoLinkFlowUid, CNeoLinkFlowFactory::NewL),
	};

EXPORT_C const TImplementationProxy* ImplementationGroupProxy(TInt& aTableCount)
	{
	aTableCount = sizeof(ImplementationTable) / sizeof(TImplementationProxy);
	return ImplementationTable;
	}

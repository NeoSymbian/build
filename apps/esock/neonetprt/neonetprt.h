// SPDX-License-Identifier: Apache-2.0
// neonetprt.h -- NEONET.PRT, ESOCK's KAfInet protocol module over NeoNet (docs wifi.md W5a): see neonetprt.cpp.
#ifndef NEONETPRT_H
#define NEONETPRT_H

#include <es_prot.h>
#include <es_prot_internal.h>
#include <in_sock.h>
#include "../../neonet/neonet.h"

// A NeoNet session shared by a socket and the connections it accepts (NeoNet's socket ids belong to a session).
class CNeoSession : public CBase
	{
public:
	static CNeoSession* NewL();
	void Open() { ++iRefs; }
	void Close() { if (--iRefs == 0) delete this; }
	RNeoNet iNet;
private:
	~CNeoSession() { iNet.Close(); }
	TInt iRefs;
	};

class CNeoSap;

// one waiting NeoNet call of a socket
class CNeoOp : public CActive
	{
public:
	enum TKind { EConnect, ERecv, ESend, EAccept };
	CNeoOp(CNeoSap& aSap, TKind aKind);
	~CNeoOp() { Cancel(); }
	void Go() { SetActive(); }
	TRequestStatus& Status() { return iStatus; }
private:
	void RunL();
	void DoCancel();
	CNeoSap& iSap;
	TKind iKind;
	};

class CNeoSap : public CServProviderBase
	{
	friend class CNeoOp;
public:
	static CNeoSap* NewL(TUint aSockType, CNeoSession* aSession = NULL);
	~CNeoSap();
	// CServProviderBase
	void SetNotify(MSocketNotify* aSocket);
	void Start();
	void LocalName(TSockAddr& aAddr) const;
	TInt SetLocalName(TSockAddr& aAddr);
	void RemName(TSockAddr& aAddr) const;
	TInt SetRemName(TSockAddr& aAddr);
	TInt GetOption(TUint aLevel, TUint aName, TDes8& aOption) const;
	void Ioctl(TUint aLevel, TUint aName, TDes8* aOption);
	void CancelIoctl(TUint aLevel, TUint aName);
	TInt SetOption(TUint aLevel, TUint aName, const TDesC8& aOption);
	void ActiveOpen();
	void ActiveOpen(const TDesC8& aConnectionData);
	TInt PassiveOpen(TUint aQueSize);
	TInt PassiveOpen(TUint aQueSize, const TDesC8& aConnectionData);
	void Shutdown(TCloseType aOption);
	void Shutdown(TCloseType aOption, const TDesC8& aDisconnectionData);
	void AutoBind();
	TUint Write(const TDesC8& aDesc, TUint aOptions, TSockAddr* aAddr = NULL);
	void GetData(TDes8& aDesc, TUint aOptions, TSockAddr* aAddr = NULL);
	TInt SecurityCheck(MProvdSecurityChecker* aChecker);
private:
	CNeoSap(TUint aSockType);
	void ConstructL(CNeoSession* aSession);
	void Done(CNeoOp::TKind aKind, TInt aResult);
	void Cancelled(CNeoOp::TKind aKind);
	TInt OpenUdp();
	void StartRecv();
	void StartSend();
	void CloseSocket();
	TBool Stream() const { return iSockType == KSockStream; }
	TUint iSockType;
	CNeoSession* iSession;
	TInt iId;								// the NeoNet socket (-1: none yet)
	TInetAddr iLocal, iRemote;
	TBool iConnected, iClosing, iEof;
	CNeoOp* iConnectOp;
	CNeoOp* iRecvOp;
	CNeoOp* iSendOp;
	CNeoOp* iAcceptOp;
	HBufC8* iRx;							// received bytes / one datagram, and how much of it ESOCK took
	TPtr8 iRxPtr;
	TInt iRxPos;
	TBool iRxReady;
	HBufC8* iTx;							// bytes in flight to NEONET
	TPtr8 iTxPtr;
	TPtrC8 iTxRest;							// what NEONET hasn't taken yet
	TInt iTxPos;
	TNeoNetEndpoint iPeer;					// a datagram's sender, an accepted connection's peer
	TNeoNetEndpoint iTo;
	};

// KAfInet name resolution over NeoNet's DNS
class CNeoResolver : public CHostResolvProvdBase
	{
	class COp : public CActive
		{
	public:
		COp(CNeoResolver& aOwner) : CActive(EPriorityStandard), iOwner(aOwner) { CActiveScheduler::Add(this); }
		~COp() { Cancel(); }
		void Go() { SetActive(); }
		TRequestStatus& Status() { return iStatus; }
	private:
		void RunL() { iOwner.Resolved(iStatus.Int()); }
		void DoCancel() { iOwner.iNet.Close(); }	// NEONET answers the waiting request with KErrCancel
		CNeoResolver& iOwner;
		};
public:
	static CNeoResolver* NewL();
	~CNeoResolver();
	void GetByName(TNameRecord& aName);
	void GetByAddress(TNameRecord& aName);
	void SetHostName(TDes& aNameBuf);
	void GetHostName(TDes& aNameBuf);
	void CancelCurrentOperation();
	TInt SecurityCheck(MProvdSecurityChecker* aChecker);
private:
	CNeoResolver() {}
	void Resolved(TInt aResult);
	RNeoNet iNet;
	COp* iOp;
	TNameRecord* iQuery;
	TBuf8<256> iName;
	TBuf8<4> iIp;
	TBuf8<256> iAnswered;					// the last name answered: a second GetByName for it is "no more"
	THostName iHostName;
	};

class CNeoProtocol : public CProtocolBase
	{
public:
	CNeoProtocol(TUint aSockType) : iSockType(aSockType) {}
	CServProviderBase* NewSAPL(TUint aSockType);
	CHostResolvProvdBase* NewHostResolverL();
	void Identify(TServerProtocolDesc* aDesc) const;
private:
	TUint iSockType;
	};

class CNeoFamily : public CProtocolFamilyBase
	{
public:
	TInt Install() { return KErrNone; }
	CProtocolBase* NewProtocolL(TUint aSockType, TUint aProtocol);
	TUint ProtocolList(TServerProtocolDesc*& aList);
	};

#endif

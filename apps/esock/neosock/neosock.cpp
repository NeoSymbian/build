// SPDX-License-Identifier: Apache-2.0
// NEOSOCK.EXE -- ESOCK over NeoNet, end to end through the 2010 socket API (docs wifi.md W5a): RSocketServ and its
// protocols, RConnection Start/Stop, RHostResolver, TCP listen/accept/connect/write/read and UDP send-to/receive-from,
// all on 127.0.0.1 when NEONET runs its loopback interface (Syborg). On a real link (the phone: smoltcp has no loopback
// there) it instead fetches http://connectivitycheck.gstatic.com/generate_204 over TCP and asks the gateway's DNS for
// that name over UDP. Prints "neosock: ..." lines and "neosock: PASS" or "neosock: FAIL <step> <error>".
#include <e32base.h>
#include <e32debug.h>
#include <es_sock.h>
#include <in_sock.h>
#include "neonet.h"

static TInt Fail(const char* aStep, TInt aErr)
	{
	RDebug::Printf("neosock: FAIL %s %d", aStep, aErr);
	return aErr < 0 ? aErr : KErrGeneral;
	}

// wait for aStatus at most aSeconds (KErrTimedOut: the request is left to the subsession's close)
static TInt Wait(TRequestStatus& aStatus, TInt aSeconds)
	{
	RTimer timer;
	if (timer.CreateLocal() != KErrNone)
		{
		User::WaitForRequest(aStatus);
		return aStatus.Int();
		}
	TRequestStatus t;
	timer.After(t, aSeconds * 1000000);
	User::WaitForRequest(aStatus, t);
	TInt r = aStatus == KRequestPending ? KErrTimedOut : aStatus.Int();
	if (t == KRequestPending)
		{
		timer.Cancel();
		User::WaitForRequest(t);
		}
	timer.Close();
	return r;
	}

// run aExe to its end (NEOCDB: CommsDat set up), or start it and leave it (NEONET)
static TInt Run(const TDesC& aExe, TBool aWait)
	{
	RProcess p;
	TInt r = p.Create(aExe, KNullDesC);
	if (r != KErrNone)
		return r;
	TRequestStatus s;
	p.Logon(s);
	p.Resume();
	if (aWait)
		{
		User::WaitForRequest(s);
		r = p.ExitType() == EExitKill ? p.ExitReason() : KErrDied;
		}
	else
		{
		p.LogonCancel(s);
		User::WaitForRequest(s);
		}
	p.Close();
	return r;
	}

static TInt Loopback(RSocketServ& aSs)
	{
	TInetAddr loop(INET_ADDR(127, 0, 0, 1), 0);
	// TCP: a listener, a client, one exchange each way
	RSocket listener, client, server;
	TInt r = listener.Open(aSs, KAfInet, KSockStream, KProtocolInetTcp);
	if (r != KErrNone)
		return Fail("tcp open", r);
	TInetAddr any(KInetAddrAny, 8081);
	if ((r = listener.Bind(any)) != KErrNone || (r = listener.Listen(1)) != KErrNone)
		return Fail("tcp listen", r);
	if ((r = server.Open(aSs)) != KErrNone)
		return Fail("blank socket", r);
	TRequestStatus accepted, connected;
	listener.Accept(server, accepted);
	if ((r = client.Open(aSs, KAfInet, KSockStream, KProtocolInetTcp)) != KErrNone)
		return Fail("tcp client open", r);
	loop.SetPort(8081);
	client.Connect(loop, connected);
	if ((r = Wait(connected, 10)) != KErrNone)
		return Fail("tcp connect", r);
	if ((r = Wait(accepted, 10)) != KErrNone)
		return Fail("tcp accept", r);
	TRequestStatus s;
	client.Write(_L8("hello"), s);
	if ((r = Wait(s, 5)) != KErrNone)
		return Fail("tcp write", r);
	TBuf8<5> buf;												// Read completes once the descriptor is full
	server.Read(buf, s);
	if ((r = Wait(s, 5)) != KErrNone || buf != _L8("hello"))
		return Fail("tcp read", r);
	server.Write(_L8("world"), s);
	if ((r = Wait(s, 5)) != KErrNone)
		return Fail("tcp write back", r);
	TSockXfrLength len;
	TBuf8<16> back;
	client.RecvOneOrMore(back, 0, s, len);
	if ((r = Wait(s, 5)) != KErrNone || back != _L8("world"))
		return Fail("tcp read back", r);
	RDebug::Printf("neosock: tcp ok (hello / world over 127.0.0.1:8081)");
	client.Close();
	server.Close();
	listener.Close();

	// UDP: one datagram
	RSocket a, b;
	if ((r = a.Open(aSs, KAfInet, KSockDatagram, KProtocolInetUdp)) != KErrNone ||
		(r = b.Open(aSs, KAfInet, KSockDatagram, KProtocolInetUdp)) != KErrNone)
		return Fail("udp open", r);
	TInetAddr port(KInetAddrAny, 9001);
	if ((r = a.Bind(port)) != KErrNone)
		return Fail("udp bind", r);
	loop.SetPort(9001);
	b.SendTo(_L8("ping"), loop, 0, s);
	if ((r = Wait(s, 5)) != KErrNone)
		return Fail("udp send", r);
	TInetAddr from;
	TBuf8<16> dgram;
	a.RecvFrom(dgram, from, 0, s);
	if ((r = Wait(s, 5)) != KErrNone || dgram != _L8("ping"))
		return Fail("udp recv", r);
	RDebug::Printf("neosock: udp ok (ping from port %d)", from.Port());
	a.Close();
	b.Close();
	return KErrNone;
	}

// a DNS query (RFC 1035) for connectivitycheck.gstatic.com, type A
static void DnsQuery(TDes8& aOut)
	{
	const TUint8 q[] = { 0x4e, 0x53, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 17, 'c', 'o', 'n', 'n', 'e', 'c', 't', 'i', 'v', 'i',
		't', 'y', 'c', 'h', 'e', 'c', 'k', 7, 'g', 's', 't', 'a', 't', 'i', 'c', 3, 'c', 'o', 'm', 0, 0, 1, 0, 1 };
	aOut.Copy(q, sizeof(q));
	}

static TInt Internet(RSocketServ& aSs, TUint32 aGateway)
	{
	RHostResolver hr;
	TInt r = hr.Open(aSs, KAfInet, KProtocolInetUdp);
	if (r != KErrNone)
		return Fail("resolver open", r);
	TNameEntry entry;
	TRequestStatus s;
	hr.GetByName(_L("connectivitycheck.gstatic.com"), entry, s);
	if ((r = Wait(s, 15)) != KErrNone)
		return Fail("resolve", r);
	hr.Close();
	TInetAddr addr(TInetAddr::Cast(entry().iAddr).Address(), 80);
	RSocket sock;
	if ((r = sock.Open(aSs, KAfInet, KSockStream, KProtocolInetTcp)) != KErrNone)
		return Fail("http open", r);
	sock.Connect(addr, s);
	if ((r = Wait(s, 20)) != KErrNone)
		return Fail("http connect", r);
	sock.Write(_L8("GET /generate_204 HTTP/1.1\r\nHost: connectivitycheck.gstatic.com\r\nConnection: close\r\n\r\n"), s);
	if ((r = Wait(s, 10)) != KErrNone)
		return Fail("http write", r);
	TBuf8<256> reply;
	TSockXfrLength len;
	sock.RecvOneOrMore(reply, 0, s, len);
	if ((r = Wait(s, 15)) != KErrNone)
		return Fail("http read", r);
	sock.Close();
	if (reply.Find(_L8(" 204")) < 0)
		return Fail("http status", KErrGeneral);
	RDebug::Printf("neosock: http ok (204 from connectivitycheck.gstatic.com)");

	RSocket udp;
	if ((r = udp.Open(aSs, KAfInet, KSockDatagram, KProtocolInetUdp)) != KErrNone)
		return Fail("dns open", r);
	TBuf8<64> query;
	DnsQuery(query);
	TInetAddr dns(aGateway, 53);
	udp.SendTo(query, dns, 0, s);
	if ((r = Wait(s, 5)) != KErrNone)
		return Fail("dns send", r);
	TBuf8<512> answer;
	TInetAddr from;
	udp.RecvFrom(answer, from, 0, s);
	if ((r = Wait(s, 10)) != KErrNone || answer.Length() < 12 || answer[0] != 0x4e)
		return Fail("dns recv", r);
	RDebug::Printf("neosock: udp ok (%d-byte DNS answer from port %d)", answer.Length(), from.Port());
	udp.Close();
	return KErrNone;
	}

static TInt RunL()
	{
	TInt r = Run(_L("neocdb.exe"), ETrue);					// CommsDat (idempotent)
	if (r != KErrNone)
		return Fail("neocdb", r);
	Run(_L("neonet.exe"), EFalse);							// NEONET (a second copy exits at once)
	RNeoNet net;												// wait (30 s at most) for it to hold an address
	TBuf8<KNeoNetStatusSize> st;
	for (TInt i = 0; i < 60; ++i)
		{
		if ((r = net.Handle() ? KErrNone : net.Connect()) == KErrNone && net.Status(st) == KErrNone &&
			st[1] == ENeoNetUp)
			break;
		User::After(500000);
		}
	if (!net.Handle() || st.Length() < 2 || st[1] != ENeoNetUp)
		return Fail("neonet up", r);
	RDebug::Printf("neosock: NeoNet at %d.%d.%d.%d", st[4], st[5], st[6], st[7]);
	TBool loopback = st[4] == 127;
	TUint32 gateway = NeoNetIp(st.Mid(8, 4));
	net.Close();
	RSocketServ ss;
	if ((r = ss.Connect()) != KErrNone)
		return Fail("socket server", r);
	TUint n = 0;
	ss.NumProtocols(n);
	for (TUint i = 1; i <= n; ++i)
		{
		TProtocolDesc d;
		if (ss.GetProtocolInfo(i, d) == KErrNone)
			{
			TBuf8<0x20> name;
			name.Copy(d.iName);
			RDebug::Printf("neosock: protocol %d: %S, family %x, type %d, protocol %d", i, &name, d.iAddrFamily,
				d.iSockType, d.iProtocol);
			}
		}
	if (n < 2)
		return Fail("protocols", n);

	RConnection conn;
	if ((r = conn.Open(ss)) != KErrNone)
		return Fail("connection open", r);
	TRequestStatus s;
	conn.Start(s);
	if ((r = Wait(s, 10)) != KErrNone)
		return Fail("connection start", r);
	RDebug::Printf("neosock: connection started");

	RHostResolver hr;
	if ((r = hr.Open(ss, KAfInet, KProtocolInetUdp)) != KErrNone)
		return Fail("resolver open", r);
	TNameEntry entry;
	hr.GetByName(_L("localhost"), entry, s);
	if ((r = Wait(s, 5)) != KErrNone || TInetAddr::Cast(entry().iAddr).Address() != INET_ADDR(127, 0, 0, 1))
		return Fail("resolve localhost", r);
	hr.Close();
	RDebug::Printf("neosock: resolver ok (localhost)");

	if ((r = loopback ? Loopback(ss) : Internet(ss, gateway)) != KErrNone)
		return r;
	conn.Stop();
	conn.Close();
	ss.Close();
	RDebug::Printf("neosock: PASS");
	return KErrNone;
	}

GLDEF_C TInt E32Main()
	{
	CTrapCleanup* cleanup = CTrapCleanup::New();
	TInt r = KErrNoMemory;
	if (cleanup)
		{
		TRAPD(e, r = RunL());
		if (e != KErrNone)
			r = Fail("leave", e);
		}
	delete cleanup;
	return r;
	}

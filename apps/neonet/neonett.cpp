// SPDX-License-Identifier: Apache-2.0
// NEONETT.EXE -- NEONET.DLL's test on the phone (docs wifi.md W7): waits for an address, resolves a name, fetches
// http://connectivitycheck.gstatic.com/generate_204 over TCP and asks the gateway's DNS for it over UDP. Prints
// "neonett: ..." lines and "neonett: PASS" or "neonett: FAIL <step> <error>" to the debug log.
#include <e32base.h>
#include <e32debug.h>
#include "neonet.h"

_LIT8(KHost, "connectivitycheck.gstatic.com");

// wait for aStatus at most aSeconds: its result, or KErrTimedOut (the request is left to the session's close)
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

static TInt Fail(const char* aStep, TInt aErr)
	{
	RDebug::Printf("neonett: FAIL %s %d", aStep, aErr);
	return aErr < 0 ? aErr : KErrGeneral;
	}

// a DNS query for KHost, type A (RFC 1035 4.1)
static void DnsQuery(TDes8& aOut)
	{
	const TUint8 head[] = { 0x4e, 0x53, 0x01, 0x00, 0, 1, 0, 0, 0, 0, 0, 0 };	// id, RD, one question
	aOut.Copy(head, sizeof(head));
	TPtrC8 rest(KHost);
	while (rest.Length())
		{
		TInt dot = rest.Locate('.');
		TPtrC8 label = dot < 0 ? rest : rest.Left(dot);
		aOut.Append((TUint8)label.Length());
		aOut.Append(label);
		rest.Set(dot < 0 ? TPtrC8() : rest.Mid(dot + 1));
		}
	const TUint8 tail[] = { 0, 0, 1, 0, 1 };											// root, type A, class IN
	aOut.Append(tail, sizeof(tail));
	}

static TInt Run()
	{
	RNeoNet net;
	TInt r = net.Connect();
	if (r != KErrNone)
		return Fail("connect", r);
	TBuf8<KNeoNetStatusSize> st;
	for (TInt i = 0; i < 60; ++i)												// up to a minute for Wi-Fi + DHCP
		{
		r = net.Status(st);
		if (r != KErrNone)
			return Fail("status", r);
		if (st[1] == ENeoNetUp)
			break;
		User::After(1000000);
		}
	if (st[1] != ENeoNetUp)
		return Fail("no address", st[1]);
	RDebug::Printf("neonett: address %d.%d.%d.%d/%d gateway %d.%d.%d.%d", st[4], st[5], st[6], st[7], st[2], st[8],
		st[9], st[10], st[11]);

	TBuf8<4> ip;
	TRequestStatus s;
	net.Resolve(KHost, ip, s);
	if ((r = Wait(s, 15)) != KErrNone)
		return Fail("resolve", r);
	RDebug::Printf("neonett: resolved %d.%d.%d.%d", ip[0], ip[1], ip[2], ip[3]);

	net.TcpConnect(NeoNetIp(ip), 80, s);
	TInt id = Wait(s, 25);
	if (id < 0)
		return Fail("tcp connect", id);
	_LIT8(KGet, "GET /generate_204 HTTP/1.1\r\nHost: connectivitycheck.gstatic.com\r\nConnection: close\r\n\r\n");
	net.Send(id, KGet, s);
	if ((r = Wait(s, 10)) <= 0)
		return Fail("send", r);
	TBuf8<512> reply;
	net.Recv(id, reply, s);
	if ((r = Wait(s, 15)) <= 0)
		return Fail("recv", r);
	TInt status = reply.Find(_L8(" 204"));
	net.CloseSocket(id);
	RDebug::Printf("neonett: http: %d bytes, %s", reply.Length(), status >= 0 ? "204" : "not 204");
	if (status < 0)
		return Fail("http status", KErrGeneral);

	TInt udp = net.UdpOpen(0);
	if (udp < 0)
		return Fail("udp open", udp);
	TBuf8<64> query;
	DnsQuery(query);
	TNeoNetEndpoint to;
	NeoNetEndpoint(to, NeoNetIp(st.Mid(8, 4)), 53);
	net.SendTo(udp, query, to, s);
	if ((r = Wait(s, 5)) != query.Length())
		return Fail("udp send", r);
	TBuf8<512> answer;
	TNeoNetEndpoint from;
	net.RecvFrom(udp, answer, from, s);
	if ((r = Wait(s, 10)) <= 12)
		return Fail("udp recv", r);
	RDebug::Printf("neonett: dns: %d bytes from port %d, id %02x%02x, %d answers", r, NeoNetPort(from), answer[0],
		answer[1], answer[7]);
	net.CloseSocket(udp);
	net.Close();
	RDebug::Printf("neonett: PASS");
	return KErrNone;
	}

GLDEF_C TInt E32Main()
	{
	return Run();
	}

/* Copyright The Phorepoc Authors
 * SPDX-License-Identifier: Apache-2.0 */
/* uidcrc.c -- drop-in for Symbian's uidcrc host tool (rcomp shells out to it).
 *   uidcrc <uid1> <uid2> <uid3> <outfile>
 * Writes the 16-byte TCheckedUid header: three UIDs + the UID checksum
 * (CRC16-CCITT of the odd bytes << 16 | CRC16-CCITT of the even bytes),
 * the same checksum the E32Image header uses. */
#include <stdio.h>
#include <stdlib.h>

static unsigned short crc16(const unsigned char *p, int n)
{
	unsigned short crc = 0;
	while (n--) {
		int i;
		crc ^= (unsigned short)(*p++ << 8);
		for (i = 0; i < 8; i++)
			crc = (crc & 0x8000) ? (unsigned short)((crc << 1) ^ 0x1021) : (unsigned short)(crc << 1);
	}
	return crc;
}

int main(int argc, char **argv)
{
	unsigned char b[16], even[6], odd[6];
	unsigned long u[3], sum;
	int i;
	FILE *f;
	if (argc != 5) {
		fprintf(stderr, "usage: uidcrc <uid1> <uid2> <uid3> <outfile>\n");
		return 1;
	}
	for (i = 0; i < 3; i++) {
		u[i] = strtoul(argv[i + 1], NULL, 0);
		b[i * 4] = (unsigned char)u[i];
		b[i * 4 + 1] = (unsigned char)(u[i] >> 8);
		b[i * 4 + 2] = (unsigned char)(u[i] >> 16);
		b[i * 4 + 3] = (unsigned char)(u[i] >> 24);
	}
	for (i = 0; i < 6; i++) {
		even[i] = b[i * 2];
		odd[i] = b[i * 2 + 1];
	}
	sum = ((unsigned long)crc16(odd, 6) << 16) | crc16(even, 6);
	b[12] = (unsigned char)sum;
	b[13] = (unsigned char)(sum >> 8);
	b[14] = (unsigned char)(sum >> 16);
	b[15] = (unsigned char)(sum >> 24);
	f = fopen(argv[4], "wb");
	if (!f)
		return 2;
	fwrite(b, 1, 16, f);
	fclose(f);
	return 0;
}

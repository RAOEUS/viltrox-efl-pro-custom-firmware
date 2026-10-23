#!/usr/bin/env python3
"""Viltrox .ecp <-> raw image codec.
File = 0x200 header + N*512 blocks ('_Best->\\0' + u32 index + 500 data bytes) + 0xFF pad to 0x12000.
Block data is obfuscated per 32-bit LE word: plain = bswap32(rol32(cipher,1)).
Flash layout: block0 = FAT dir+version text (info, 500B), block1 = 0xFF, blocks 2.. = app at 0x08020400 (contiguous 500B chunks).
"""
import struct,sys
MAGIC=b'_Best->\0'
def rol(x,n): return ((x<<n)|(x>>(32-n)))&0xffffffff
def ror(x,n): return ((x>>n)|(x<<(32-n)))&0xffffffff
def dec(buf):
    return b''.join(struct.pack('>I',rol(c,1)) for (c,) in struct.iter_unpack('<I',buf))
def enc(buf):
    return b''.join(struct.pack('<I',ror(p,1)) for (p,) in struct.iter_unpack('>I',buf))
def unpack(ecp):
    hdr=ecp[:0x200]
    total,applen,ver=struct.unpack_from('<III',hdr,0x64)
    nblk=(total-0x200)//512
    blocks=[]
    for i in range(nblk):
        b=ecp[0x200+i*512:0x200+(i+1)*512]
        assert b[:8]==MAGIC and struct.unpack('<I',b[8:12])[0]==i, f'bad block {i}'
        blocks.append(dec(b[12:]))
    info=blocks[0]; app=b''.join(blocks[2:])
    assert blocks[1]==b'\xff'*500
    return hdr,info,app,ver
def pack(info,app,ver,filesize=0x12000):
    assert len(info)==500
    app=app+b'\xff'*((-len(app))%500)
    blocks=[info,b'\xff'*500]+[app[i:i+500] for i in range(0,len(app),500)]
    total=0x200+len(blocks)*512
    hdr=bytearray(b'\xff'*0x200)
    c=b'Copyright of VILTROX Technology Co., Ltd.\0'; hdr[:len(c)]=c
    struct.pack_into('<III',hdr,0x64,total,len(app),ver)
    out=bytes(hdr)+b''.join(MAGIC+struct.pack('<I',i)+enc(d) for i,d in enumerate(blocks))
    assert len(out)<=filesize
    return out+b'\xff'*(filesize-len(out))
if __name__=='__main__':
    src=open(sys.argv[1],'rb').read()
    hdr,info,app,ver=unpack(src)
    print('blocks',(struct.unpack_from('<I',hdr,0x64)[0]-0x200)//512,'ver',hex(ver),'applen',hex(len(app)))
    re=pack(info,app,ver)
    print('ROUNDTRIP', 'OK' if re==src else 'MISMATCH')
    if re!=src:
        d=[i for i in range(len(src)) if src[i]!=re[i]]; print('first diffs',[hex(x) for x in d[:10]],len(d))

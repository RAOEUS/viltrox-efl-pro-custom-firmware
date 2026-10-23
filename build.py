#!/usr/bin/env python3
"""Build the two custom .ecp firmwares from Viltrox's original 'EF-L ver1.2 For AF Lens.ecp'.
The original is NOT part of this repository: download it from Viltrox and put it next to this script.
Needs arm-none-eabi-gcc (set ARM_GCC=/path/to/bin or have it on PATH)."""
import hashlib,os,struct,subprocess,sys
R=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,f'{R}/tools'); import ecp
ORIG=f'{R}/EF-L ver1.2 For AF Lens.ecp'
ORIG_SHA256='07e7cc065a4208e8b77fd8433f4d49aa4e94c34274f25a58b4c4b9db599e5644'
BASE=0x08020400
if not os.path.exists(ORIG):
    sys.exit(f"missing {ORIG}\nDownload 'EF-L/L PRO V1.2 For AF lens' from Viltrox's download centre and place the .ecp here.")
if hashlib.sha256(open(ORIG,'rb').read()).hexdigest()!=ORIG_SHA256:
    sys.exit('the original .ecp does not match the v1.2 AF-lens firmware this patch was made for; refusing to patch it')
GCC=os.environ.get('ARM_GCC',''); GCC=GCC+'/' if GCC else ''
os.makedirs(f'{R}/build',exist_ok=True)
subprocess.check_call([f'{GCC}arm-none-eabi-gcc','-mcpu=cortex-m4','-mthumb','-Os','-ffreestanding','-nostdlib','-fno-builtin',
    '-fno-asynchronous-unwind-tables','-Wall','-Wextra','-T',f'{R}/src/link.ld','-o',f'{R}/build/autocal.elf',f'{R}/src/autocal.c'])
subprocess.check_call([f'{GCC}arm-none-eabi-objcopy','-O','binary',f'{R}/build/autocal.elf',f'{R}/build/autocal.bin'])
blob=open(f'{R}/build/autocal.bin','rb').read()
hdr,info,app,ver=ecp.unpack(open(ORIG,'rb').read())
open(f'{R}/build/app_orig_0x08020400.bin','wb').write(app)
def put(img,addr,data):
    o=addr-BASE; assert 0<=o and o+len(data)<=len(img), hex(addr); img[o:o+len(data)]=data
def put32(img,addr,v): put(img,addr,struct.pack('<I',v))
def check32(img,addr,v): assert struct.unpack_from('<I',img,addr-BASE)[0]==v, f'expected {v:#x} at {addr:#x}'
def info_text(tag):
    i=bytearray(info); t=(b'Ver1.2\r\n2021.11.24\r\n'+tag.encode()+b'\r\n').ljust(len(info)-64,b'\xff'); i[64:]=t; return bytes(i)

# Variant A: auto-calibration add-on. Code appended at 0x0802D9E0 (3 extra 500-byte blocks),
# lens-init step list pointer in FUN_0802591c (literal @0x0802597c) redirected to our list.
a=bytearray(app)+b'\xff'*1500
assert a[0x0802D9E0-BASE:0x0802D9E0-BASE+len(blob)]==b'\xff'*len(blob)
put(a,0x0802D9E0,blob); check32(a,0x0802597c,0x0802a7f4); put32(a,0x0802597c,0x0802D9E0)
imgA=bytes(a[:0xDCB4]); open(f'{R}/build/app_autocal.bin','wb').write(imgA)
open(f'{R}/EF-L ver1.2 AF autocal.ecp','wb').write(ecp.pack(info_text('custom: autocal unknown lenses'),imgA,ver))

# Variant B: compact. Table B (8 x 10 bytes @0x0802A1CC) moved to 0x0802D9E0 (free tail), its pointer in
# FUN_08025c28 (literal @0x08025CAC) updated; Table A grows by one entry into the old Table B slot:
# EF 24-70mm f/2.8L USM (Canon lens ID 230 -> key 0xE600, 24-70mm) using the 24-70 II profile block @0x080287A4;
# loop bound 'cmp r2,#0x3a' @0x08025C62 -> #0x3b. Block count unchanged.
b=bytearray(app)
tabB=bytes(b[0x0802a1cc-BASE:0x0802a1cc-BASE+80]); assert b[0x0802D9E0-BASE:0x0802D9E0-BASE+80]==b'\xff'*80
put(b,0x0802D9E0,tabB); check32(b,0x08025cac,0x0802a1cc); put32(b,0x08025cac,0x0802D9E0)
put(b,0x0802a1cc,struct.pack('<HHHI',0xe600,24,70,0x080287a4))
assert b[0x08025c62-BASE:0x08025c62-BASE+2]==bytes.fromhex('3a2a'); put(b,0x08025c62,bytes.fromhex('3b2a'))
imgB=bytes(b); open(f'{R}/build/app_compact.bin','wb').write(imgB)
open(f'{R}/EF-L ver1.2 AF plus24-70mk1.ecp','wb').write(ecp.pack(info_text('custom: +EF24-70 2.8L mk1'),imgB,ver))
for n in ('EF-L ver1.2 AF autocal.ecp','EF-L ver1.2 AF plus24-70mk1.ecp'):
    d=open(f'{R}/{n}','rb').read(); h,i,ap,v=ecp.unpack(d)
    nb=(struct.unpack_from('<I',h,0x64)[0]-0x200)//512; txt=i[64:120].rstrip(b'\xff')
    print(f'{n}: {len(d)} bytes, blocks={nb}, app={len(ap):#x}, info={txt!r}')

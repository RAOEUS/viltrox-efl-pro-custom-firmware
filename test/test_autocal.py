"""Unicorn test: run autocal_step tick-by-tick against a simulated EF lens."""
import struct
from unicorn import *
from unicorn.arm_const import *
import os; R=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); img=open(f'{R}/build/app_autocal.bin','rb').read()
BASE=0x08020400; STEP=struct.unpack_from('<I',img,0x0802D9E0-BASE+36)[0]; SEND=0x080229dc; APPLY=0x08024c80
RET=0x0806f000; NEXT=0x0806f100
mu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
mu.mem_map(0x08020000,0x20000); mu.mem_write(BASE,img)
mu.mem_map(0x20000000,0x20000); mu.mem_map(0x40000000,0x1000); mu.mem_map(RET&~0xfff,0x1000)
mu.mem_write(RET,b'\x70\x47'*2); mu.mem_write(NEXT,b'\x01\x20\x70\x47')  # stubs; g_next returns 1
next_calls=[0]
def hn(uc,a,sz,ud): next_calls[0]+=1
mu.hook_add(UC_HOOK_CODE,hn,begin=NEXT,end=NEXT)
# initial RAM contents: run the firmware's own Keil .data decompressor (scatter record @0x0802D898)
orig=open(f'{R}/build/app_orig_0x08020400.bin','rb').read()
_m=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS); _m.mem_map(0x08020000,0x20000); _m.mem_write(BASE,orig); _m.mem_map(0x20000000,0x20000); _m.mem_map(0x0806f000,0x1000); _m.mem_write(0x0806f000,b'\x00\xbe')
_m.reg_write(UC_ARM_REG_R0,0x0802d8b8); _m.reg_write(UC_ARM_REG_R1,0x20000000); _m.reg_write(UC_ARM_REG_R2,0x9fc); _m.reg_write(UC_ARM_REG_SP,0x20007400); _m.reg_write(UC_ARM_REG_LR,0x0806f001)
try: _m.emu_start(0x080205d1,0x0806f000,count=2000000)
except UcError: pass
mu.mem_write(0x20000000,bytes(_m.mem_read(0x20000000,0x9fc)))
def w8(a,v): mu.mem_write(a,bytes([v&0xff]))
def r8(a): return mu.mem_read(a,1)[0]
def r16(a): return struct.unpack('<H',mu.mem_read(a,2))[0]
def r32(a): return struct.unpack('<I',mu.mem_read(a,4))[0]
mu.mem_write(0x200002d0,struct.pack('<I',NEXT|1))
mu.mem_write(0x200009e8,struct.pack('<I',84000000)); mu.mem_write(0x4000002c,struct.pack('<I',84*139))
# simulated lens state
lens={'pos':1234,'target':None,'moving':0,'sent':[],'applied':None}
import sys
scn=sys.argv[1] if len(sys.argv)>1 else 'zoom'
zoom=(scn=='zoom')
w8(0x20000343,1 if scn=='known' else 0); w8(0x20000332,0 if scn=='detach' else 1); w8(0x20000348,1 if zoom else 0); w8(0x2000032c,1 if scn=='zoom' else 0)
mu.mem_write(0x2000030e,struct.pack('<HH',24,70) if zoom else struct.pack('<HH',85,85)); mu.mem_write(0x20000308,struct.pack('<H',0xe600))
mu.mem_write(0x20000108,b'\xff'*64)
pending=None   # byte to deliver at next tick into *g_rxptr
def hook(uc,addr,size,ud):
    global pending
    if addr==SEND:
        b=uc.reg_read(UC_ARM_REG_R0)&0xff; lens['sent'].append(b)
        # reply to THIS byte arrives next tick; compute reply based on command context
        ctx=lens.get('ctx'); 
        if b==0x06: lens['target']=3000 if scn=='reversed' else 0; lens['moving']=8; pending=0x06; lens['ctx']=None
        elif b==0x05: lens['target']=0 if scn=='reversed' else 3000; lens['moving']=8; pending=0x05; lens['ctx']=None
        elif b==0x50: lens['ctx']=('spd',0); pending=0x50
        elif b==0x90: lens['ctx']=('st',0); pending=0x90
        elif b==0x07: lens['moving']=0; pending=0x07
        elif b==0xc0: lens['ctx']=('c0',0); pending=0xc0
        elif b==0xc2: lens['ctx']=('c2',0); pending=0xc2
        elif ctx and ctx[0]=='spd': lens['ctx']=None; pending=b; assert b==0x60, b
        elif b==0 and ctx:
            kind,i=ctx
            if kind=='st': pending=(0x80 if scn=='mf' else 0) if i==1 else 0
            elif kind=='c0':
                if scn=='stuck': lens['pos']+=1
                pending=(lens['pos']>>8)&0xff if i==0 else lens['pos']&0xff
            else: pending=[0x01,0x7c,0x00,0x26][i]   # max 380cm, min 38cm
            lens['ctx']=(kind,i+1)
        else: pending=0
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    elif addr==APPLY:
        p=uc.reg_read(UC_ARM_REG_R0); lens['applied']=p
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
mu.hook_add(UC_HOOK_CODE,hook,begin=SEND,end=SEND)
mu.hook_add(UC_HOOK_CODE,hook,begin=APPLY,end=APPLY)
ticks=0; delays=0
while True:
    # ISR: deliver pending byte, then advance lens motion (if the tick was a delay, time passes)
    if pending is not None: w8(r32(0x200004c4),pending); pending=None
    arr=r32(0x4000002c)
    if arr>84*1000:   # a delay tick: lens moves
        delays+=1
        if lens['moving']: 
            lens['moving']-=1; lens['pos']+= (lens['target']-lens['pos'])//max(1,lens['moving'])
    mu.reg_write(UC_ARM_REG_SP,0x20007000); mu.reg_write(UC_ARM_REG_LR,RET|1)
    mu.emu_start(STEP,RET,count=100000)
    r=mu.reg_read(UC_ARM_REG_R0); ticks+=1
    if r==1 or ticks>20000: break
print('ticks',ticks,'delays',delays,'ret',r,'bytes sent',len(lens['sent']),'first',lens['sent'][:12],'last',lens['sent'][-6:])
print('g_sub',r8(0x20000492),'g_cmd',r8(0x20000491),'rxptr',hex(r32(0x200004c4)),'ARR restored',r32(0x4000002c)==84*139)
print('next_calls',next_calls[0]); assert r==1 and next_calls[0]==1
if scn=='detach':
    assert lens['applied'] is None and not lens['sent'] and r8(0x20000492)==0; print('DETACH OK'); sys.exit(0)
if scn=='reversed':
    blk=struct.unpack('<20H',mu.mem_read(lens['applied'],40)); name=bytes(mu.mem_read(0x20000108,64)).split(b'\0')[0]
    print('name',name); assert blk[10]==1500 and b'!R' in name and r16(0x200002ee)==0x1000; print('REVERSED OK'); sys.exit(0)
if scn in ('mf','stuck'):
    blk=struct.unpack('<20H',mu.mem_read(lens['applied'],40)); name=bytes(mu.mem_read(0x20000108,64)).split(b'\0')[0]
    print('blk',blk,'name',name,'sent',len(lens['sent']),'stops',lens['sent'].count(7))
    assert blk[10]==1500 and ((scn=='mf' and b'!M' in name and len(lens['sent'])==3 and r16(0x200002ee)==0) or (scn=='stuck' and b'!T' in name and lens['sent'].count(7)==2 and r16(0x200002ee)==0)); print(scn.upper(),'OK'); sys.exit(0)
if scn=='known':
    assert lens['applied'] is None and not lens['sent']; print('KNOWN PASSTHROUGH OK'); sys.exit(0)
assert lens['applied']==0x20007440+0x1c, hex(lens['applied'] or 0)
blk=struct.unpack('<41H',mu.mem_read(lens['applied'],82))
if not zoom:
    print('name',bytes(mu.mem_read(0x20000108,64)).split(b'\0')[0]); assert blk[0]==9 and blk[10]==3000 and blk[9]==850 and blk[19]==0; name=bytes(mu.mem_read(0x20000108,64)).split(b'\0')[0]; print('dist',blk[1:10],'steps',blk[10:20],'name',name); assert name.endswith(b'E') and lens['sent'].count(0x50)==2; print('PRIME OK'); sys.exit(0)
print('block hdr',blk[0],'dist',[(-1 if v==0xffff else v) for v in blk[1:10]],'steps',blk[10:20],'M',blk[20],'focals',blk[21:41])
print('name:',bytes(mu.mem_read(0x20000108,64)).split(b'\0')[0])
print('pos',hex(r16(0x200002ee)),'lastc0',r16(0x20000316),'lens final pos',lens['pos'])

assert blk[0]==9 and blk[10]==3000 and blk[19]==0 and blk[20]==20 and blk[21]==24 and blk[40]==70
assert all(blk[i]>blk[i+1] for i in range(2,9)) and all(blk[i]>=blk[i+1] for i in range(10,19))
assert lens['sent'][:5]==[0x90,0,0,0x50,0x60] and lens['sent'].count(0x50)==2; print('TEST OK')

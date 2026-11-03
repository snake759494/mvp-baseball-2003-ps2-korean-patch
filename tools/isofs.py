import struct,sys
def walk(f,lba=None,size=None,path=''):
    if lba is None:
        f.seek(16*2048);pvd=f.read(2048)
        lba,size=struct.unpack_from('<I',pvd,158)[0],struct.unpack_from('<I',pvd,166)[0]
    f.seek(lba*2048);d=f.read(size);p=0;out=[]
    while p<len(d):
        n=d[p]
        if n==0: p=(p//2048+1)*2048;continue
        l,s=struct.unpack_from('<I',d,p+2)[0],struct.unpack_from('<I',d,p+10)[0]
        fl=d[p+25];nm=d[p+33:p+33+d[p+32]]
        if nm not in(b'\0',b'\1'):
            nm=nm.decode('latin1').split(';')[0]
            if fl&2: out+=walk(f,l,s,path+nm+'/')
            else: out.append((path+nm,l,s,lba*2048+p))
        p+=n
    return out
if __name__=='__main__':
    for e in walk(open(sys.argv[1],'rb')): print(*e)

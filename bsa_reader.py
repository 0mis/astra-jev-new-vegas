"""Small read-only BSA104 reader for inspecting locally owned UI definitions.

Original implementation of documented archive fields. No archive writes or
automatic extraction paths; callers explicitly choose any local output file.
"""
import pathlib,struct,zlib

class Archive:
    def __init__(self,path):
        self.path=pathlib.Path(path)
        with self.path.open('rb') as source:
            header=source.read(36)
            magic,version,offset,self.flags,folders,files,folder_names,file_names,_=struct.unpack('<4s8I',header)
            if magic!=b'BSA\0' or version!=104 or folders>100000 or files>1000000:
                raise ValueError('Unsupported or unbounded BSA header')
            if self.flags&3!=3:raise ValueError('Named folders and files required')
            source.seek(offset)
            records=[struct.unpack('<QII',source.read(16)) for _ in range(folders)]
            pending=[]
            for _,count,_ in records:
                length=source.read(1)[0]
                folder=source.read(length).rstrip(b'\0').decode('cp1252')
                if len(pending)+count>files:raise ValueError('Too many file records')
                for _ in range(count):
                    _,size,position=struct.unpack('<QII',source.read(16))
                    pending.append((folder,size,position))
            if len(pending)!=files or file_names>64*1024*1024:raise ValueError('Invalid file name table')
            names=source.read(file_names).split(b'\0')
            if len(names)!=files+1:raise ValueError('File name count mismatch')
            self.entries={folder+'\\'+name.decode('cp1252'):(size,position) for (folder,size,position),name in zip(pending,names)}

    def read(self,name,max_bytes=2*1024*1024):
        size,position=self.entries[name];compressed=bool(size&0x40000000)^bool(self.flags&4);size&=0x3fffffff
        if size>max_bytes+4096:raise ValueError('Entry exceeds inspection bound')
        with self.path.open('rb') as source:
            source.seek(position);raw=source.read(size)
        if len(raw)!=size:raise ValueError('Truncated archive entry')
        if self.flags&0x100:raw=raw[1+raw[0]:]
        if compressed:
            expected=struct.unpack('<I',raw[:4])[0]
            if expected>max_bytes:raise ValueError('Expanded entry exceeds bound')
            decoder=zlib.decompressobj();raw=decoder.decompress(raw[4:],max_bytes+1)
            if not decoder.eof or len(raw)!=expected:raise ValueError('Expanded entry size mismatch')
        if len(raw)>max_bytes:raise ValueError('Entry exceeds inspection bound')
        return raw

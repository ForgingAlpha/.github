"""Explicit local fixture Git/provider data; these are never hosted observations."""
import base64
import hashlib
import json
import subprocess


def blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def context(values):
    result=[]
    for name in ('PROJECT.md','AGENTS.md','CLAUDE.md'):
        item=values.get(name)
        if item is None: result.append({'path':name,'kind':'absent'})
        elif item[0]=='120000':result.append({'path':name,'kind':'symlink','target':item[1].decode()})
        else:result.append({'path':name,'kind':'file','sha256':hashlib.sha256(item[1]).hexdigest()})
    return result


def seed_file(api, repo, revision, name, data, mode='100644'):
    """Augment deliberately synthetic provider trees, preserving S1 fixture IDs."""
    commit=api.gets.setdefault(f'repos/{repo}/git/commits/{revision}',{'tree':{'sha':hashlib.sha1((revision+'tree').encode()).hexdigest()},'parents':[]})
    oid=commit['tree']['sha'];parts=name.split('/')
    for i,part in enumerate(parts):
        entries=api.gets.setdefault(f'repos/{repo}/git/trees/{oid}',{'truncated':False,'tree':[]})['tree']
        item=next((x for x in entries if x['path']==part),None)
        if i<len(parts)-1:
            if item is None:
                item={'path':part,'mode':'040000','type':'tree','sha':hashlib.sha1((oid+part).encode()).hexdigest()};entries.append(item)
            oid=item['sha']
        else:
            if item is not None:entries.remove(item)
            if data is not None:
                oid=blob(data);entries.append({'path':part,'mode':mode,'type':'blob','sha':oid})
                api.gets[f'repos/{repo}/git/blobs/{oid}']={'encoding':'base64','size':len(data),'content':base64.b64encode(data).decode()}


def git_data(root, repo, revisions):
    """Complete exact object responses derived from actual fixture Git objects."""
    def git(*args):return subprocess.check_output(['git',*args],cwd=root)
    gets={}
    for revision in revisions:
        tree=git('rev-parse',revision+'^{tree}').decode().strip()
        parents=git('show','-s','--format=%P',revision).decode().split()
        gets[f'repos/{repo}/git/commits/{revision}']={'tree':{'sha':tree},'parents':[{'sha':x} for x in parents]}
        pending=[tree]
        while pending:
            oid=pending.pop()
            key=f'repos/{repo}/git/trees/{oid}'
            if key in gets:continue
            entries=[]
            for raw in git('ls-tree','-z',oid).split(b'\0'):
                if not raw:continue
                meta,name=raw.split(b'\t');mode,kind,child=meta.decode().split();name=name.decode()
                entries.append({'path':name,'mode':mode,'type':kind,'sha':child})
                if kind=='tree':pending.append(child)
                else:
                    data=git('cat-file','blob',child)
                    gets[f'repos/{repo}/git/blobs/{child}']={'encoding':'base64','size':len(data),'content':base64.b64encode(data).decode()}
            gets[key]={'truncated':False,'tree':entries}
    return gets


def git_context(root, revision):
    values={}
    for name in ('PROJECT.md','AGENTS.md','CLAUDE.md'):
        info=subprocess.check_output(['git','ls-tree',revision,'--',name],cwd=root).decode().split()
        if info:values[name]=(info[0],subprocess.check_output(['git','show',revision+':'+name],cwd=root))
    return context(values)

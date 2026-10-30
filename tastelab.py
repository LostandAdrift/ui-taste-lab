#!/usr/bin/env python3
"""UI Taste Lab: local reference review, CLI and JSON API. Python 3.11+."""
import xml.etree.ElementTree as ET
import re
import argparse, contextlib, hashlib, json, mimetypes, os, secrets, shutil, sqlite3, tempfile, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DEFAULT = Path.home() / 'forge/referneces/ui-taste-lab'
WEB = Path(__file__).parent / 'web'
VOTES = {'love', 'like', 'dislike', 'skip'}
EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.avif'}

def now(): return datetime.now(timezone.utc).isoformat()
def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f: f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def connect(root):
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / 'taste.sqlite3', timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''CREATE TABLE IF NOT EXISTS items (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT DEFAULT '', image TEXT DEFAULT '',
      tags TEXT DEFAULT '{}', added TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS feedback (
      seq INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL, vote TEXT NOT NULL,
      note TEXT DEFAULT '', created TEXT NOT NULL, undone INTEGER DEFAULT 0);
      CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS discovery_days (day TEXT PRIMARY KEY, count INTEGER NOT NULL);''')
    return db

def items(db):
    result=[]
    for row in db.execute('''SELECT i.*, f.vote, f.note, f.seq FROM items i LEFT JOIN feedback f ON
      f.seq=(SELECT MAX(seq) FROM feedback WHERE item_id=i.id AND undone=0) ORDER BY i.added DESC, i.id'''):
        r=dict(row); r['tags']=json.loads(r['tags']); result.append(r)
    return result

def add(db, root, title, source='', image=None, tags=None, discovery_day=None):
    if source and urlparse(source).scheme not in ('https','http'): raise ValueError('Source must use http or https')
    image_name=''
    if image:
        path=Path(image).expanduser().resolve()
        if path.suffix.lower() not in EXTS or not path.is_file(): raise ValueError('Unsupported image file')
        if path.stat().st_size > 40*1024*1024: raise ValueError('Image exceeds 40 MB')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        image_name=f'objects/{digest[:2]}/{digest}{path.suffix.lower()}'
        target=root/image_name; target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            fd,tmp=tempfile.mkstemp(dir=target.parent); os.close(fd)
            try: shutil.copyfile(path,tmp); os.replace(tmp,target)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
        key=digest
    else: key=hashlib.sha256(source.encode()).hexdigest()
    if not source and not image: raise ValueError('An image or source is required')
    if not isinstance(tags or {},dict): raise ValueError('Tags must be an object')
    db.execute('BEGIN IMMEDIATE')
    try:
        if db.execute('SELECT 1 FROM items WHERE id=?',(key,)).fetchone():
            db.commit(); return None
        queue=db.execute('''SELECT COUNT(*) FROM items i WHERE NOT EXISTS
          (SELECT 1 FROM feedback f WHERE f.item_id=i.id AND f.undone=0)''').fetchone()[0]
        if queue >= 100:
            db.commit(); return None
        if discovery_day:
            row=db.execute('SELECT count FROM discovery_days WHERE day=?',(discovery_day,)).fetchone()
            if row and row[0]>=20:
                db.commit(); return None
        db.execute('INSERT INTO items VALUES (?,?,?,?,?,?)',(key,str(title)[:500],source,image_name,json.dumps(tags or {}),now()))
        if discovery_day:
            db.execute('INSERT INTO discovery_days VALUES (?,1) ON CONFLICT(day) DO UPDATE SET count=count+1',(discovery_day,))
        db.commit(); return key
    except Exception:
        db.rollback(); raise

def vote(db, item_id, value, note=''):
    if value not in VOTES: raise ValueError('Unknown vote')
    if not db.execute('SELECT 1 FROM items WHERE id=?',(item_id,)).fetchone(): raise ValueError('Unknown item')
    if len(note)>4000: raise ValueError('Note too long')
    db.execute('INSERT INTO feedback(item_id,vote,note,created) VALUES (?,?,?,?)',(item_id,value,note,now()));db.commit()

def undo(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        event=db.execute('SELECT * FROM feedback WHERE undone=0 ORDER BY seq DESC LIMIT 1').fetchone()
        if event:
            prior=db.execute('SELECT 1 FROM feedback WHERE item_id=? AND undone=0 AND seq<?',(event['item_id'],event['seq'])).fetchone()
            pending=sum(not i['vote'] for i in items(db))
            if not prior and pending>=100: raise ValueError('Queue is full. Review a reference before undoing this reaction.')
            db.execute('UPDATE feedback SET undone=1 WHERE seq=?',(event['seq'],))
        db.commit()
    except Exception:
        db.rollback();raise

def profile(db):
    allitems=items(db)
    explicit=db.execute("SELECT value FROM settings WHERE key='preferences'").fetchone()
    out=['# UI Taste Lab — taste evidence','', 'Use these references to inform Proofanvil. Preferences are evidence, not universal design rules.', '', '## Explicit preferences', explicit[0] if explicit else 'No explicit global preferences recorded.', '', '## Reference feedback']
    for i in allitems:
        if i['vote']:
            out += [f"- {i['vote'].upper()}: {i['title']} [id: {i['id']}]",f"  Source: {i['source'] or 'local reference'}",f"  Tags: {json.dumps(i['tags'],ensure_ascii=False)}",f"  Note (scoped to this reference): {i['note'] or '(none)'}"]
    out+=['','## Inferred patterns (tentative)','These are descriptive counts, not explicit global preferences. Dislikes do not imply rejecting every tag on a reference.']
    counts={}
    for i in allitems:
        if i['vote'] in ('love','like'):
            for k,v in i['tags'].items():
                for val in (v if isinstance(v,list) else [v]): counts.setdefault(f'{k}: {val}',[]).append(i['id'])
    for tag,ids in sorted(counts.items(),key=lambda p:-len(p[1])):
        if len(ids)>=2: out.append(f'- Positive association: {tag} ({len(ids)} references); evidence: '+', '.join(ids))
    return '\n'.join(out)+'\n'

def export(db, root):
    data={'schema_version':1,'exported_at':now(),'items':items(db),'events':[dict(r) for r in db.execute('SELECT * FROM feedback ORDER BY seq')]}
    atomic(root/'exports/feedback.json',json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    atomic(root/'exports/TASTE.md',profile(db)); return data

def import_manifest(db,root,path,discovery_day=None):
    raw=Path(path).read_text()
    records=[json.loads(line) for line in raw.splitlines() if line.strip()] if Path(path).suffix=='.jsonl' else json.loads(raw)
    ids=[]
    if not isinstance(records,list): raise ValueError('Manifest must be an array')
    for r in records:
        image=r.get('image')
        if image and not Path(image).is_absolute(): image=str(Path(path).resolve().parent/image)
        tags=dict(r.get('tags',{}))
        for field in ('snippet','provenance','discovered_at'):
            if r.get(field): tags[field]=r[field]
        key=add(db,root,r['title'],r.get('source',r.get('url','')),image,tags,discovery_day)
        if key: ids.append(key)
    return ids

def discover(db,root,manifest=None,online=False):
    from zoneinfo import ZoneInfo
    day=datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
    inbox=root/'inbox';inbox.mkdir(exist_ok=True)
    paths=[manifest] if manifest else sorted(inbox.glob('*.json'))
    ids=[]; errors=[]
    for path in paths:
        try: ids.extend(import_manifest(db,root,path,day))
        except (OSError,ValueError,KeyError) as e: errors.append({'source':str(path),'error':str(e)})
    if online:
        registry=json.loads((Path(__file__).parent/'sources.json').read_text())
        buckets=[]
        for source in registry['sources']:
            if not source.get('automated'): continue
            try:
                req=urllib.request.Request(source['url'],headers={'User-Agent':'UI-Taste-Lab/0.1 (local-first design inspiration)','Accept':'application/json, application/rss+xml, application/xml'})
                with urllib.request.urlopen(req,timeout=20) as response:
                    raw=response.read(4*1024*1024+1)
                if len(raw)>4*1024*1024:raise ValueError('Source exceeds 4 MB response limit')
                candidates=[]
                if source['adapter']=='github-repositories':
                    for repo in json.loads(raw).get('items',[]):
                        candidates.append((repo['full_name'],repo['html_url'],{'platform':'web','placement':source['placement'],'provenance':'GitHub public repository API','license':(repo.get('license') or {}).get('spdx_id','unknown'),'preview':'link-only'}))
                elif source['adapter']=='rss':
                    for entry in ET.fromstring(raw).findall('.//item'):
                        link=entry.findtext('link')
                        if not link:continue
                        candidates.append((entry.findtext('title') or link,link,{'platform':'web','placement':source['placement'],'provenance':source['url'],'published_at':entry.findtext('pubDate') or '', 'snippet':re.sub('<[^>]+>','',entry.findtext('description') or '')[:500],'preview':'link-only'}))
                buckets.append(candidates)
            except (OSError,ValueError,KeyError,ET.ParseError) as e: errors.append({'source':source['name'],'error':str(e)})
        # Round-robin sources so a single prolific feed cannot consume the batch.
        while any(buckets):
            for bucket in buckets:
                if not bucket:continue
                title,url,tags=bucket.pop(0)
                try:
                    key=add(db,root,title,url,tags=tags,discovery_day=day)
                    if key: ids.append(key)
                except ValueError as e: errors.append({'source':url,'error':str(e)})
    report={'day':day,'new_count':len(ids),'new_ids':ids,'queue_count':sum(not i['vote'] for i in items(db)), 'daily_limit':20,'queue_limit':100,'errors':errors,'mode':'online-links' if online else 'local-inbox'}
    atomic(root/'exports/last-discovery.json',json.dumps(report,indent=2)+'\n')
    return report

def serve(root,port):
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,status,data,ctype='application/json'):
            body=data if isinstance(data,bytes) else json.dumps(data).encode()
            self.send_response(status); self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
            self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(body)
        def valid(self):
            return self.headers.get('Host') in {f'127.0.0.1:{port}',f'localhost:{port}'}
        def do_GET(self):
            if not self.valid(): return self.send(403,{'error':'Invalid host'})
            path=urlparse(self.path).path
            with contextlib.closing(connect(root)) as db:
                if path=='/api/items': return self.send(200,items(db))
                if path=='/api/session':
                    pref=db.execute("SELECT value FROM settings WHERE key='preferences'").fetchone()
                    return self.send(200,{'token':token,'root':str(root),'preferences':pref[0] if pref else ''})
                if path=='/api/profile': return self.send(200,profile(db).encode(),'text/plain; charset=utf-8')
                if path=='/api/export': return self.send(200,export(db,root))
            if path.startswith('/media/'):
                file=(root/path.removeprefix('/media/')).resolve()
                if not file.is_relative_to((root/'objects').resolve()): return self.send(403,{})
            else:
                file=WEB/({'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(path,'__missing__'))
            if not file.is_file(): return self.send(404,{'error':'Not found'})
            self.send(200,file.read_bytes(),mimetypes.guess_type(file)[0] or 'application/octet-stream')
        def do_POST(self):
            if not self.valid() or self.headers.get('X-Taste-Token')!=token: return self.send(403,{'error':'Missing session token'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size>20000: raise ValueError('Request too large')
                body=json.loads(self.rfile.read(size))
                with contextlib.closing(connect(root)) as db:
                    if self.path=='/api/vote': vote(db,body['id'],body['vote'],body.get('note',''))
                    elif self.path=='/api/undo': undo(db)
                    elif self.path=='/api/tags':
                        tags=body['tags']
                        if not isinstance(tags,dict):raise ValueError('Tags must be an object')
                        db.execute('UPDATE items SET tags=? WHERE id=?',(json.dumps(tags),body['id']));db.commit()
                    elif self.path=='/api/add': add(db,root,body['title'],body['source'],tags=body.get('tags',{}))
                    elif self.path=='/api/preferences':
                        db.execute("INSERT OR REPLACE INTO settings VALUES ('preferences',?)",(str(body['text'])[:10000],));db.commit()
                    else: return self.send(404,{})
                    export(db,root)
                self.send(200,{'ok':True})
            except (ValueError,KeyError,TypeError) as e:self.send(400,{'error':str(e)})
    print(f'UI Taste Lab: http://127.0.0.1:{port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,default=DEFAULT)
    sub=parser.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('serve');s.add_argument('--port',type=int,default=7841)
    s=sub.add_parser('ingest');s.add_argument('folder',type=Path)
    s=sub.add_parser('import');s.add_argument('manifest',type=Path)
    s=sub.add_parser('discover',help='Idempotently import permitted-source manifests from inbox/; no scraping');s.add_argument('--manifest',type=Path);s.add_argument('--online',action='store_true',help='Discover public MIT repository links using GitHub API; no third-party screenshots downloaded')
    s=sub.add_parser('import-candidates',help='Import JSON/JSONL web-search records, daily and queue caps enforced');s.add_argument('manifest',type=Path)
    s=sub.add_parser('pending-count')
    s=sub.add_parser('vote');s.add_argument('id');s.add_argument('vote',choices=sorted(VOTES));s.add_argument('--note',default='')
    s=sub.add_parser('preferences');s.add_argument('text')
    for cmd in ['list','export','profile']:sub.add_parser(cmd)
    a=parser.parse_args();root=a.data.expanduser().resolve()
    with contextlib.closing(connect(root)) as db:
        if a.cmd=='serve':return serve(root,a.port)
        if a.cmd=='ingest':
            result=[]
            for path in sorted(a.folder.expanduser().rglob('*')):
                if path.is_file() and path.suffix.lower() in EXTS and not path.resolve().is_relative_to(root):result.append(add(db,root,path.stem,image=path,tags={'placement':'unclassified'}))
            print(json.dumps({'imported_ids':result}))
        elif a.cmd=='pending-count':print(json.dumps({'pending_count':sum(not i['vote'] for i in items(db)),'queue_limit':100}))
        elif a.cmd=='import-candidates':
            report=discover(db,root,a.manifest);print(json.dumps(report));export(db,root)
            if report['errors']:raise SystemExit(1)
        elif a.cmd=='import':print(json.dumps(import_manifest(db,root,a.manifest)))
        elif a.cmd=='discover':
            report=discover(db,root,a.manifest,a.online);print(json.dumps(report))
            export(db,root)
            if report['errors']:raise SystemExit(1)
        elif a.cmd=='vote':vote(db,a.id,a.vote,a.note)
        elif a.cmd=='preferences':db.execute("INSERT OR REPLACE INTO settings VALUES ('preferences',?)",(a.text,));db.commit()
        elif a.cmd=='list':print(json.dumps(items(db),indent=2))
        elif a.cmd=='profile':print(profile(db))
        if a.cmd!='list' and a.cmd!='profile':export(db,root)
if __name__=='__main__':main()

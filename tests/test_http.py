import base64,json,socket,subprocess,sys,tempfile,time,unittest,urllib.request,urllib.error
from pathlib import Path
class HttpTests(unittest.TestCase):
    def test_local_api_upload_vote_undo_and_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'tastelab.py'),'--data',temp,'serve','--port',str(port)],stdout=subprocess.PIPE)
            try:
                self.assertIn(b'UI Taste Lab',process.stdout.readline())
                base=f'http://127.0.0.1:{port}'
                def request(path,body=None,headers=None):
                    h=headers or {};data=None
                    if body is not None:data=json.dumps(body).encode();h={'Content-Type':'application/json',**h}
                    return urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=h),timeout=5)
                session=json.load(request('/api/session'));headers={'X-Taste-Token':session['token']}
                with self.assertRaises(urllib.error.HTTPError) as error:request('/api/add',{'title':'blocked','source':'https://example.org'})
                self.assertEqual(error.exception.code,403);error.exception.close()
                pixel=base64.b64encode(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII=')).decode()
                request('/api/upload',{'title':'Original test pixel','filename':'pixel.png','image':pixel,'tags':{'placement':'test'}},headers).close()
                item=json.load(request('/api/items'))[0]
                self.assertEqual(request('/media/'+item['image']).headers['Content-Type'],'image/png')
                request('/api/vote',{'id':item['id'],'vote':'love','note':'Test note'},headers).close()
                self.assertEqual(json.load(request('/api/items'))[0]['vote'],'love')
                request('/api/undo',{},headers).close();self.assertIsNone(json.load(request('/api/items'))[0]['vote'])
                with self.assertRaises(urllib.error.HTTPError) as error:request('/api/items',headers={'Host':'evil.invalid'})
                self.assertEqual(error.exception.code,403);error.exception.close()
                with self.assertRaises(urllib.error.HTTPError) as error:request('/media/../taste.sqlite3')
                self.assertEqual(error.exception.code,403);error.exception.close()
                self.assertIn('UI Taste Lab',request('/').read().decode())
            finally:process.terminate();process.wait(timeout=5);process.stdout.close()

import concurrent.futures, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tastelab as t
class TasteTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=t.connect(self.root)
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def add(self,n=0,**kw):return t.add(self.db,self.root,'Reference '+str(n),f'https://example.org/{n}',**kw)
    def test_dedupe(self):self.assertIsNotNone(self.add());self.assertIsNone(self.add());self.assertEqual(len(t.items(self.db)),1)
    def test_vote_and_undo(self):
        key=self.add();t.vote(self.db,key,'love','Warm lighting');t.vote(self.db,key,'dislike','Only the cramped icons')
        self.assertEqual(t.items(self.db)[0]['vote'],'dislike')
        self.db.execute('UPDATE feedback SET undone=1 WHERE seq=2');self.db.commit()
        self.assertEqual(t.items(self.db)[0]['vote'],'love');self.assertIn('Warm lighting',t.profile(self.db))
    def test_scope_and_evidence(self):
        for i in range(2):t.vote(self.db,self.add(i,tags={'placement':'inventory'}),'like','Nice spacing')
        text=t.profile(self.db);self.assertIn('tentative',text);self.assertIn('evidence:',text);self.assertIn('scoped to this reference',text)
    def test_daily_limit(self):
        for i in range(25):self.add(i,discovery_day='2026-10-30')
        self.assertEqual(len(t.items(self.db)),20)
    def test_concurrent_queue_cap(self):
        for i in range(98):self.add(i)
        def work(i):
            db=t.connect(self.root)
            try:return t.add(db,self.root,str(i),f'https://example.org/{i}')
            finally:db.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(work,range(100,130)))
        self.assertEqual(len(t.items(self.db)),100)
    def test_preserve_reviewed(self):
        for i in range(100):self.add(i)
        key=t.items(self.db)[0]['id'];t.vote(self.db,key,'love');self.assertIsNotNone(self.add(101));self.assertEqual(len(t.items(self.db)),101)
    def test_import_jsonl(self):
        path=self.root/'records.jsonl';path.write_text(json.dumps({'title':'Menu','url':'https://example.org/menu','snippet':'Visual hierarchy','provenance':'web search','tags':{'placement':'navigation'}})+'\n')
        report=t.discover(self.db,self.root,path);self.assertEqual(report['new_count'],1);self.assertEqual(t.discover(self.db,self.root,path)['new_count'],0)
        self.assertIn('web search',t.items(self.db)[0]['tags']['provenance'])
    def test_undo_preserves_cap(self):
        first=self.add(0);t.vote(self.db,first,'love')
        for i in range(1,101):self.add(i)
        with self.assertRaises(ValueError):t.undo(self.db)
        self.assertEqual(sum(not i['vote'] for i in t.items(self.db)),100)
    def test_undo_normal(self):
        key=self.add();t.vote(self.db,key,'love');t.undo(self.db)
        self.assertIsNone(t.items(self.db)[0]['vote'])
    def test_reject_bad_sources(self):
        with self.assertRaises(ValueError):t.add(self.db,self.root,'bad','javascript:alert(1)')
    def test_export(self):
        self.add();t.export(self.db,self.root);self.assertEqual(json.loads((self.root/'exports/feedback.json').read_text())['schema_version'],1)
if __name__=='__main__':unittest.main()

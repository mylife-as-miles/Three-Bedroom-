import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corpus import DC,fnv1a64
class BytecodeProperties(unittest.TestCase):
 def dc(self):
  dc=DC.__new__(DC);dc.path='synthetic';dc.db={fnv1a64('f'):'f',fnv1a64('g'):'g',fnv1a64('item'):'item',fnv1a64('counter'):'counter'};dc.b=bytes(16)+b''.join(struct.pack('<Q',fnv1a64(s)) for s in ['f','g','item','counter']);dc.text=len(dc.b);dc.strings=len(dc.b);dc.reloc=b'\0';return dc
 def trace(self,ins):return self.dc().calls({'id':'synthetic@0','instruction_offset':0,'contexts':[]},ins,16)[0]
 def test_fnv_known_vectors(self):
  self.assertEqual(fnv1a64(''),0xcbf29ce484222325);self.assertEqual(fnv1a64('hello'),0xa430d84680aabd0b);self.assertNotEqual(fnv1a64('Item'),fnv1a64('item'))
 def test_global_lookup_is_not_literal(self):
  cs=self.trace([(21,0,0,0),(20,1,3,0),(67,49,1,0),(28,0,0,1),(0,0,0,0)])
  self.assertEqual(cs[0]['target'],('sid','f'));self.assertEqual(cs[0]['arguments'],[('global-ref','counter')])
 def test_literal_sid_argument(self):
  cs=self.trace([(21,0,0,0),(74,1,2,0),(67,49,1,0),(28,0,0,1),(0,0,0,0)])
  self.assertEqual(cs[0]['arguments'],[('sid','item')])
 def test_branch_disagreement_does_not_invent_target(self):
  cs=self.trace([(46,3,10,0),(21,0,0,0),(45,4,0,0),(21,0,1,0),(28,0,0,0),(0,0,0,0)])
  self.assertEqual(cs[0]['target'],('unknown',))
 def test_branch_agreement_preserves_target(self):
  cs=self.trace([(46,3,10,0),(21,0,0,0),(45,4,0,0),(21,0,0,0),(28,0,0,0),(0,0,0,0)])
  self.assertEqual(cs[0]['target'],('sid','f'))
 def test_pointer_requires_relocation(self):
  dc=self.dc();self.assertFalse(dc.ptr(16));dc.reloc=b'\x04';self.assertTrue(dc.ptr(16));self.assertFalse(dc.ptr(17))
 def test_vector_declaration_stays_vector(self):
  dc=self.dc();dc.b=bytes(16)+struct.pack('<4f',0,0,0,1);dc.text=len(dc.b);self.assertEqual(dc.decl_value('vector',16),('vector',[0.0,0.0,0.0,1.0]))
if __name__=='__main__':unittest.main()

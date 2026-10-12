#!/usr/bin/env python3
"""Copy only small derived metadata/check results into the reviewable experiment."""
import json, platform, shutil
from pathlib import Path
from build import ROOT, HERE
BASE=ROOT/'.private/experiments/drawer-diagnostics'
OUT=HERE/'evidence';OUT.mkdir(exist_ok=True)
for source,target in [('build/build.json','build.json'),('build/static-validation.json','static-validation.json'),
                      ('roundtrip-run/roundtrip.json','roundtrip.json'),('toolchain/provenance.json','toolchain.json')]:
    shutil.copyfile(BASE/source,OUT/target)
log=(BASE/'tests.log').read_text()
if 'Ran 6 tests' not in log or not log.rstrip().endswith('OK'):raise ValueError('Static test log does not show a complete pass')
(OUT/'test-results.json').write_text(json.dumps({'suite':'test_static.py','tests_passed':6,
  'execution_kind':'Python structural checks and mocked bytecode prefix only',
  'game_executed':False,'original_assets_in_version_control':False},indent=2)+'\n')
(BASIS:=OUT/'runtime-matrix.json').write_text(json.dumps({'game_executed':False,
  'environment':{'os':platform.system(),'input_scope':'script archive/extracted dc1 only; no runnable game install','wine_available':bool(shutil.which('wine'))},
  'windows_build_status':'NOT RUN','loader_integration_status':'NOT VERIFIED; no loader installed or mod deployed',
  'cases':[{'id':i,'case':case,'status':'NOT RUN','baseline_recording':None,'instrumented_recording':None,'result':None}
   for i,case in enumerate(['unmodified baseline','instrumented with F2 off','F2 toggle and other drawer isolation',
   'normal standing opening','crouched interaction','item pickup with empty/available inventory',
   'pickup with full capacity for the applicable item','drawer with no remaining item',
   'cancel/evade interruption','being attacked interruption','normal exit and control restoration',
   'save/reload and package removal'],1)]},indent=2)+'\n')
print('Published derived metadata only; runtime cases remain NOT RUN.')

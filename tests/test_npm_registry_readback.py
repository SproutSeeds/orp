from pathlib import Path
import subprocess
from orp_test_support import IsolatedTestCase

ROOT = Path(__file__).resolve().parents[1]


class NpmRegistryReadbackTests(IsolatedTestCase):
    def check_node(self, body):
        script = '''
const assert = require('node:assert/strict');
const {waitForPublishedCandidate: verify} = require(process.argv[1]);
const expected = {integrity:'sha512-tested',version:'0.5.0-rc.2',channel:'next',previousLatest:'0.4.38',attempts:3,delayMs:0};
const good = {integrity:'sha512-tested',tags:{next:'0.5.0-rc.2',latest:'0.4.38'}};
(async () => {
''' + body + "\n})().catch(error => { console.error(error); process.exitCode=1; });"
        result = subprocess.run(['node', '-e', script, str(ROOT/'scripts/npm-registry-readback.js')], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_waits_for_registry_visibility(self):
        self.check_node("let reads=0,waits=0; assert.deepEqual(await verify({...expected, read:()=>++reads<3?null:good, wait:async()=>{waits++;}}),good); assert.equal(reads,3); assert.equal(waits,2);")

    def test_waits_for_channel_propagation(self):
        self.check_node("let reads=0; assert.deepEqual(await verify({...expected, read:()=>++reads<2?{...good,tags:{latest:'0.4.38',next:'0.5.0-rc.1'}}:good}),good); assert.equal(reads,2);")

    def test_conflicting_bytes_fail_immediately(self):
        self.check_node("let reads=0; await assert.rejects(verify({...expected,read:()=>{reads++;return {...good,integrity:'sha512-other'};}}),/Registry bytes differ/); assert.equal(reads,1);")

    def test_stable_tag_change_fails_immediately(self):
        self.check_node("let reads=0; await assert.rejects(verify({...expected,read:()=>{reads++;return {...good,tags:{...good.tags,latest:'0.5.0-rc.2'}};}}),/Stable latest unexpectedly changed/); assert.equal(reads,1);")

    def test_read_error_is_not_mistaken_for_propagation(self):
        self.check_node("await assert.rejects(verify({...expected,read:()=>{throw Error('registry authentication failure');}}),/authentication failure/);")

    def test_absence_has_bounded_retry_count(self):
        self.check_node("let reads=0,waits=0; await assert.rejects(verify({...expected,read:()=>{reads++;return null;},wait:async()=>{waits++;}}),/verification window/); assert.equal(reads,3); assert.equal(waits,2);")

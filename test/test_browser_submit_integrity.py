"""Focused deferred-response regression; native extension evidence is separate."""

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class BrowserSubmitIntegrityTests(unittest.TestCase):
    def test_pending_review_cannot_approve_changed_text_duplicates_or_malformed_results(self):
        self.assertIsNotNone(shutil.which("node"), "Node is required for the browser adapter checks")
        script = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('integrations/browser_extension/content.js', 'utf8');
const outstanding = [], sent = [], panels = [];
const target = {value:'original clean prompt', isConnected:true};
let button, simulateDisabled=false;
const context = vm.createContext({
  console, setTimeout, clearTimeout, Set, Date,
  chrome: {storage:{sync:{get:async()=>({reviewBeforeSubmit:true})},onChanged:{addListener(){}}},
           runtime:{onMessage:{addListener(){}},sendMessage:()=>new Promise(r=>outstanding.push(r))}},
  document:{addEventListener(){}}, window:{location:{hostname:'chatgpt.com'},confirm:()=>true}
});
vm.runInContext(source, context);
context.target=target; context.panels=panels;
function event(){return {prevented:false,preventDefault(){this.prevented=true;},stopImmediatePropagation(){}};}
button={isConnected:true,click(){
  if(simulateDisabled)return;
  const e=event();context.guardPromptSubmit(e,target,button);
  if(!e.prevented)sent.push(target.value);
}};
context.button=button;
vm.runInContext('showPanel = text => panels.push(text); ' +
 'findPromptTarget=()=>target; findSubmitButton=()=>button;',context);
const allowed={ok:true,result:{findings:[],send_allowed:true,policy_decision:{decision:'allow',send_allowed:true}}};
(async()=>{
 await Promise.resolve();
 let review=context.guardPromptSubmit(event(),target,button);
 target.value='unreviewed synthetic private text';outstanding.shift()(allowed);await review;
 assert.deepEqual(sent,[]);assert(panels.some(p=>p.includes('changed during review')));
 target.value='original clean prompt';
 review=context.guardPromptSubmit(event(),target,button);
 const duplicate=context.guardPromptSubmit(event(),target,button);
 assert.equal(outstanding.length,1);outstanding.shift()(allowed);await Promise.all([review,duplicate]);
 assert.deepEqual(sent,['original clean prompt']);sent.length=0;
 review=context.guardPromptSubmit(event(),target,button);outstanding.shift()({ok:true,result:{}});await review;
 assert.deepEqual(sent,[]);assert(panels.some(p=>p.includes('invalid backend')));
 simulateDisabled=true;review=context.guardPromptSubmit(event(),target,button);
 outstanding.shift()(allowed);await review;
 simulateDisabled=false;review=context.guardPromptSubmit(event(),target,button);
 assert.equal(outstanding.length,1);outstanding.shift()(allowed);await review;
 assert.deepEqual(sent,['original clean prompt']);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

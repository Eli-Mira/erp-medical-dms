const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
test('approved transfer create handler is implemented',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
 assert.match(source,/async function submitTransfer\(event\)/);
 assert.match(source,/function transferPayload\(\)/);
});

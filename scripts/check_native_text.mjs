import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';

const containers = new Set(['View','Pressable','ScrollView','SafeAreaView','KeyboardAvoidingView']);
export function rawNativeText(source, filename='component.tsx') {
  const tree=ts.createSourceFile(filename,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
  const failures=[];
  function visit(node) {
    if(ts.isJsxElement(node)&&containers.has(node.openingElement.tagName.getText(tree))) {
      for(const child of node.children) {
        // JSX keeps single-line whitespace between expressions as a string.
        // Newline-only indentation is removed by the JSX transform.
        const raw=ts.isJsxText(child)?child.text:null;
        const expr=ts.isJsxExpression(child)?child.expression:null;
        if((raw!==null&&(raw.trim()||(!/[\r\n]/.test(raw)&&raw.length))) ||
           (expr&&(ts.isStringLiteral(expr)||ts.isNumericLiteral(expr)))) {
          failures.push({file:filename,line:tree.getLineAndCharacterOfPosition(child.pos).line+1});
        }
      }
    }
    ts.forEachChild(node,visit);
  }
  visit(tree);return failures;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const root=fileURLToPath(new URL('../',import.meta.url));
  const roots=['apps/teacher-mobile','apps/parent-mobile','apps/student-mobile','packages/communications-ui'];
  const failures=[];
  function walk(folder) {
    for(const entry of fs.readdirSync(folder,{withFileTypes:true})) {
      if(['node_modules','dist','.expo'].includes(entry.name))continue;
      const filename=path.join(folder,entry.name);
      if(entry.isDirectory())walk(filename);
      else if(filename.endsWith('.tsx'))failures.push(...rawNativeText(fs.readFileSync(filename,'utf8'),path.relative(root,filename)));
    }
  }
  for(const dir of roots)walk(path.join(root,dir));
  for(const item of failures)console.error(`${item.file}:${item.line}: raw text inside native container; wrap in Text or remove whitespace`);
  if(failures.length)process.exitCode=1;
  else console.log('PASS native JSX: no literal text children in native containers');
}

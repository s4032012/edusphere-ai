import {test} from 'node:test';
import assert from 'node:assert/strict';
import {rawNativeText} from '../check_native_text.mjs';
test('detects native raw strings, including the attendance whitespace regression',()=>{
  for(const jsx of ['<View>{busy&&<Spinner/>} {error&&<Text>{error}</Text>}</View>',
    '<Pressable>Save</Pressable>','<View>{" "}</View>','<View>{0}</View>']) {
    assert.equal(rawNativeText(jsx).length,1,jsx);
  }
});
test('allows text inside Text, newline indentation and web content',()=>{
  for(const jsx of ['<View>\n<Text>Hello {name}!</Text>\n{busy&&<Spinner/>}\n</View>',
    '<p>Hello <button>Save</button></p>','<View><Text>Present</Text></View>']) {
    assert.deepEqual(rawNativeText(jsx),[]);
  }
});

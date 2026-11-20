// [CODE-COLORS] 외부 라이브러리 없이 읽기용 소스에만 색을 입힙니다. 원문은 실행하지 않습니다.
// HTML 특수문자를 먼저 이스케이프하므로 SQL 값·주석 속 태그도 텍스트로만 표시됩니다.
(() => {
  const escape=text=>String(text).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const keywords=new Set(('SELECT FROM WHERE AND OR NOT NULL IS IN AS CASE WHEN THEN ELSE END BETWEEN WITH UNION ALL JOIN LEFT RIGHT INNER OUTER ON GROUP BY HAVING ORDER ASC DESC DISTINCT INTO INSERT UPDATE DELETE MERGE VALUES SET CREATE REPLACE ALTER DROP TABLE PROCEDURE FUNCTION PACKAGE VIEW BEGIN DECLARE IF ELSIF LOOP FOR WHILE RETURN EXCEPTION RAISE OPEN CLOSE USING DEFAULT CONVERSION ERROR AUTHID CURRENT_USER IN OUT CONSTANT NUMBER VARCHAR2 CLOB SYS_REFCURSOR COMMIT ROLLBACK TRUE FALSE DEF CLASS IMPORT TRY EXCEPT FINALLY RAISE PASS LAMBDA WITH YIELD NONE ELIF FROM AS ASYNC AWAIT CONST LET VAR FUNCTION NEW THROW CATCH FINALLY RETURN BREAK CONTINUE EXPORT DEFAULT OF IN TYPEOF INSTANCEOF THIS NULL TRUE FALSE').split(' '));
  function language(path=''){
    if(/\.py$/i.test(path))return 'python';if(/\.html?$/i.test(path))return 'html';
    if(/\.js$/i.test(path))return 'javascript';if(/\.json$/i.test(path))return 'json';
    if(/\.ps1$/i.test(path))return 'powershell';if(/\.css$/i.test(path))return 'css';return 'sql';
  }
  // CSV 적재 예제처럼 큰 원문은 토큰별 DOM을 만들지 않고 전체 텍스트를 보존합니다.
  const MAX_HIGHLIGHT_LENGTH=64000;
  function html(value,path=''){
    const text=String(value??'');if(text.length>MAX_HIGHLIGHT_LENGTH)return escape(text);
    const lang=language(path);let out='',i=0;
    const token=(kind,part)=>kind?part.split('\n').map(line=>'<span class="syntax-'+kind+'">'+escape(line)+'</span>').join('\n'):escape(part);
    while(i<text.length){
      const rest=text.slice(i);let kind='',length=1,match;
      if(rest.startsWith('<!--')){kind='comment';const end=text.indexOf('-->',i+4);length=end<0?text.length-i:end+3-i;}
      else if(rest.startsWith('/*')){kind='comment';const end=text.indexOf('*/',i+2);length=end<0?text.length-i:end+2-i;}
      else if((lang==='sql'&&rest.startsWith('--'))||(['javascript','css'].includes(lang)&&rest.startsWith('//'))||(['python','powershell'].includes(lang)&&rest[0]==='#')){kind='comment';const end=text.indexOf('\n',i);length=end<0?text.length-i:end-i;}
      else if(lang==='sql'&&/^q'/i.test(rest)&&rest.length>3){const start=rest[2],end=({'[':']','(':')','{':'}','<':'>'})[start]||start;const pos=text.indexOf(end+"'",i+3);kind='string';length=pos<0?text.length-i:pos+2-i;}
      else if(lang==='python'&&(rest.startsWith('"""')||rest.startsWith("'''"))){const quote=rest.slice(0,3),pos=text.indexOf(quote,i+3);kind='string';length=pos<0?text.length-i:pos+3-i;}
      else if(rest[0]==="'"||rest[0]==='"'||(lang==='javascript'&&rest[0]==='`')){
        const quote=rest[0];let end=i+1;
        while(end<text.length){if(lang!=='sql'&&text[end]==='\\'){end+=2;continue;}if(text[end]===quote){if(lang==='sql'&&text[end+1]===quote){end+=2;continue;}end++;break;}end++;}
        kind='string';length=end-i;
      }
      else if(lang==='html'&&(match=rest.match(/^<\/?[A-Za-z][^>]*>/))){kind='tag';length=match[0].length;}
      else if((match=rest.match(/^:[A-Za-z][A-Za-z0-9_]*/))){kind='bind';length=match[0].length;}
      else if((match=rest.match(/^(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?/i))){kind='number';length=match[0].length;}
      else if((match=rest.match(/^[A-Za-z_$][A-Za-z0-9_$]*/))){length=match[0].length;kind=keywords.has(match[0].toUpperCase())?'keyword':/^\s*\(/.test(rest.slice(length))?'function':'';}
      out+=token(kind,text.slice(i,i+length));i+=length;
    }
    return out;
  }
  function paint(element,value,path=''){
    const text=String(value??'');
    if(text.length>MAX_HIGHLIGHT_LENGTH)element.textContent=text;
    else element.innerHTML=html(text,path);
    element.classList.add('syntax-code');
    element.dataset.highlight=text.length>MAX_HIGHLIGHT_LENGTH?'plain':'syntax';
  }
  globalThis.CodeHighlight={html,paint,language};
  if(typeof document!=='undefined')document.querySelectorAll('code.language-sql').forEach(element=>paint(element,element.textContent));
})();

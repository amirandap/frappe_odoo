import{d as R,p as b,bi as T,e as v,f as k,h as H,j as D,Q as w,b4 as M}from"./index-e0df1d24.js";const F=["srcdoc"],N=R({__name:"EmailContent",props:{content:{type:String,required:!0}},setup(x){const E=x,m=b(null),i=b(T(E.content)),A=v(()=>{const e=document.querySelectorAll('link[rel="stylesheet"]');for(const o of e){const t=o.getAttribute("href");if(t!=null&&t.includes("/assets/helpdesk/desk/")&&t.endsWith(".css"))return t}return"/assets/helpdesk/desk/index.css"}),l=new DOMParser().parseFromString(i.value,"text/html"),C=l.querySelectorAll("div.gmail_quote"),S=l.querySelectorAll("div#appendonsend"),_=l.querySelectorAll("p.reply-to-content");if(l.body.children.length===0){const e=l.body.innerHTML.replace(/\n\n/g,`
`);i.value=`<div class="whitespace-pre-wrap">${e}</div>`}else C.length?i.value=f(l,"div.gmail_quote",!0):S.length?i.value=f(l,"div#appendonsend"):_.length&&(i.value=f(l,"p.reply-to-content"));function f(e,o,t=!1){function n(r){const a=r.querySelectorAll(o);if(a.length===0)return;const d=a[0];q(d,t),n(r)}return n(e),e.body.innerHTML}function q(e,o){var d,p,s;if(!e)return;const t=Math.random().toString(36).substring(2,7),n=l.createElement("div");n.classList.add("replied-content");const r=l.createElement("label");r.classList.add("collapse"),r.setAttribute("for",t),r.innerHTML="...",n.appendChild(r);const a=l.createElement("input");if(a.setAttribute("id",t),a.setAttribute("class","replyCollapser"),a.setAttribute("type","checkbox"),n.appendChild(a),o){const c=e.previousElementSibling;c&&c.tagName==="BR"&&c.remove();const u=e.cloneNode(!0);u.classList.remove("gmail_quote"),n.appendChild(u)}else{const c=Array.from(((d=e.parentElement)==null?void 0:d.children)||[]),u=c.indexOf(e),y=c.slice(u+1);if(y.length===0)return;const K=y.map(h=>h.cloneNode(!0)),g=l.createElement("div");g.append(...K),n.append(g);for(let h=u+1;h<c.length;h++)(p=e.parentElement)==null||p.removeChild(c[h])}(s=e.parentElement)==null||s.replaceChild(n,e)}const L=v(()=>`
  <!DOCTYPE html>
  <html>
  <head>
    <link rel="stylesheet" href="${A.value}" />
    <base target="_blank" />
    <style>
      :root {
        --bg-surface-gray-3: #ededed;
        --bg-surface-gray-4: #e2e2e2;
      }
      [data-theme='dark'] {
        --bg-surface-gray-3: #343434;
        --bg-surface-gray-4: #424242;
      }
      .replied-content .collapse {
        margin: 10px 0 10px 0;
        visibility: visible;
        cursor: pointer;
        display: flex;
        font-size: larger;
        font-weight: 700;
        height: 12px;
        line-height: 0.1;
        color: #383838;
        background: #e8eaed;
        width: 23px;
        justify-content: center;
        border-radius: 5px;
      }
      .replied-content .collapse:hover {
        background: #dadce0;
      }
      [data-theme='dark'] .replied-content .collapse {
        color: #e2e2e2;
        background: #424242;
      }
      [data-theme='dark'] .replied-content .collapse:hover {
        background: #525252;
      }
      .replied-content .collapse + input {
        display: none;
      }
      .replied-content .collapse + input + div {
        display: none;
      }
      .replied-content .collapse + input:checked + div {
        display: block;
      }
      .email-content {
        word-break: break-word;
      }
      .email-content :is(:where(img):not(:where([class~='not-prose'], [class~='not-prose'] *))) {
        border-width: 0;
      }
      .email-content :where(img):not(:where([class~='not-prose'], [class~='not-prose'] *)) {
        margin: 0;
      }
      .email-content :where(blockquote p:first-of-type):not(:where([class~='not-prose'], [class~='not-prose'] *))::before {
        content: none;
      }
      .email-content :where(blockquote p:last-of-type):not(:where([class~='not-prose'], [class~='not-prose'] *))::after {
        content: none;
      }
    </style>
  </head>
  <body>
    <div class="email-content prose-f">${i.value}</div>
  </body>
  </html>
  `);return k(m,e=>{e&&(e.onload=()=>{var a,d,p;const o=(a=e.contentWindow)==null?void 0:a.document.querySelector(".email-content");if(!o)return;const t=o.closest("html");if(!t)return;t.setAttribute("data-theme",w.value);const n=M(i.value);n&&o.classList.add(n),e.style.height=t.offsetHeight+1+"px",(d=e.contentDocument)==null||d.addEventListener("pointerdown",()=>{document.dispatchEvent(new PointerEvent("pointerdown",{bubbles:!0}))}),(p=e.contentDocument)==null||p.addEventListener("keydown",s=>{document.dispatchEvent(new KeyboardEvent("keydown",{key:s.key,code:s.code,ctrlKey:s.ctrlKey,metaKey:s.metaKey,shiftKey:s.shiftKey,altKey:s.altKey,bubbles:!0}))});const r=o.querySelectorAll(".replyCollapser");r.length&&r.forEach(s=>{s.addEventListener("change",()=>{e.style.height=t.offsetHeight+1+"px"})})})}),k(w,e=>{var t,n;const o=(n=(t=m.value)==null?void 0:t.contentDocument)==null?void 0:n.documentElement;o&&o.setAttribute("data-theme",e)}),(e,o)=>(H(),D("iframe",{ref_key:"iframeRef",ref:m,srcdoc:L.value,class:"prose-f block h-10 max-h-[500px] w-full"},null,8,F))}});export{N as _};
//# sourceMappingURL=EmailContent.vue_vue_type_script_setup_true_lang-dc1b8a8d.js.map

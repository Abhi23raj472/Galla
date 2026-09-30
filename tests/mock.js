window.__dl=[];
(()=>{
 const K="mockdb"; let data={}; try{data=JSON.parse(localStorage.getItem(K))||{}}catch{}
 if(localStorage.getItem("mockmode")==="off"){return}
 const save=()=>localStorage.setItem(K,JSON.stringify(data));
 const L=[]; const notify=()=>setTimeout(()=>L.forEach(l=>l()),0);
 const cl=o=>o===undefined?undefined:JSON.parse(JSON.stringify(o));
 const snap=p=>({id:p.split("/").pop(),exists:p in data,data:()=>cl(data[p]),metadata:{fromCache:false,hasPendingWrites:false}});
 function doc(p){if(p.split("/").length%2)throw new TypeError("odd doc path "+p);return {id:p.split("/").pop(),path:p,get:async()=>snap(p),
   set:async d=>{if(typeof d!=="object"||Array.isArray(d))throw {code:"invalid_argument"};data[p]=cl(d);save();notify()},
   update:async d=>{data[p]={...data[p],...cl(d)};save();notify()},delete:async()=>{delete data[p];save();notify()},
   onSnapshot:n=>{const l=()=>n(snap(p));L.push(l);setTimeout(l,0);return()=>{}},collection:s=>col(p+"/"+s)}}
 function col(p){if(p.split("/").length%2===0)throw new TypeError("even col path "+p);const n=p.split("/").length+1;
   const docs=()=>Object.keys(data).filter(k=>k.startsWith(p+"/")&&k.split("/").length===n).sort().map(snap);
   return {path:p,doc:id=>doc(p+"/"+(id||Math.random().toString(36).slice(2))),
     onSnapshot:nx=>{const l=()=>{const d=docs();nx({docs:d,size:d.length,empty:!d.length,docChanges:()=>[],metadata:{fromCache:false,hasPendingWrites:false}})};L.push(l);setTimeout(l,0);return()=>{}}}}
 const api={db:{doc,collection:col},user:{id:async()=>"u1",isOwner:()=>true},downloads:{save:async r=>{window.__dl.push(r);return{status:"saved"}}}};
 window.claude={use:async n=>api[n]||null};
})();

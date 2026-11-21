let ctx;
const LOGO_GEOMETRY=/*LOGO_GEOMETRY*/null;
const INK="#0E0E11",MUTED="#6B6B74",ACC="#5546FF",GREY="#B4B4BE";
const CAMPC={A:"#A855F7",B:"#5546FF",C:"#7C9CFF"};
function rng(seed){return()=>{seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
const lerp=(a,b,k)=>a+(b-a)*k;
function hexA(h,a){const n=parseInt(h.slice(1),16);return`rgba(${n>>16&255},${n>>8&255},${n&255},${a})`}
function rr(c,x,y,w,h,r){c.beginPath();c.roundRect(x,y,w,h,r)}
function txt(s,x,y,{size=40,weight=400,color=INK,align="left",ls=0,base="alphabetic"}={}){ctx.font=`${weight} ${size}px "Geist"`;ctx.fillStyle=color;ctx.textAlign=align;ctx.textBaseline=base;ctx.letterSpacing=ls+"px";ctx.fillText(s,x,y);ctx.letterSpacing="0px"}
function wrap(text,x,y,maxW,lh,o){ctx.font=`${o.weight||400} ${o.size}px "Geist"`;ctx.letterSpacing=(o.ls||0)+"px";const words=text.split(" ");let line="",yy=y;const lines=[];for(const w of words){const test=line?line+" "+w:w;if(ctx.measureText(test).width>maxW&&line){lines.push(line);line=w}else line=test}if(line)lines.push(line);ctx.letterSpacing="0px";lines.forEach((l,i)=>txt(l,x,y+i*lh,o));return y+(lines.length-1)*lh}

function aura(blobs,bg="#FFFFFF"){
  const w=ctx.canvas.width,h=ctx.canvas.height;ctx.fillStyle=bg;ctx.fillRect(0,0,w,h);
  for(const [x,y,r,c,a] of blobs){const g=ctx.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,hexA(c,a));g.addColorStop(.55,hexA(c,a*.45));g.addColorStop(1,hexA(c,0));ctx.fillStyle=g;ctx.fillRect(0,0,w,h)}
}
function softAura(x,y,r,a=1){aura([[x,y,r,"#7B6CFF",.13*a],[x+r*.45,y+r*.22,r*.7,"#9AA8FF",.11*a]])}

const TINTS=[[248,70,88,76],[232,60,90,80],[262,55,90,78],[240,40,92,82],[255,65,88,74],[226,55,91,79],[270,45,90,80],[244,50,93,83],[236,65,89,77]];
const DOMAINS=["witryna-1.test","oferta-dnia.test","news-24.test","portal-7.test","wiadomosci.test","okazja-pl.test","raport-x.test","info-now.test","strona-9.test"];
function card(x,y,s,v,a=1,{shadow=true}={}){
  const w=360,h=250,[hue,sat,l1,l2]=TINTS[v%TINTS.length];
  ctx.save();ctx.globalAlpha*=a;ctx.translate(x,y);ctx.scale(s,s);
  if(shadow){ctx.shadowColor="rgba(30,30,70,.10)";ctx.shadowBlur=60;ctx.shadowOffsetY=22}
  ctx.fillStyle="#fff";rr(ctx,-w/2,-h/2,w,h,26);ctx.fill();
  ctx.shadowColor="transparent";ctx.strokeStyle="#ECECF2";ctx.lineWidth=1.2;ctx.stroke();
  const g=ctx.createLinearGradient(-w/2,-h/2,w/2,-h/2+130);g.addColorStop(0,`hsl(${hue} ${sat}% ${l1}%)`);g.addColorStop(1,`hsl(${hue+18} ${sat}% ${l2}%)`);
  ctx.fillStyle=g;rr(ctx,-w/2+16,-h/2+16,w-32,118,16);ctx.fill();
  ctx.fillStyle="rgba(255,255,255,.85)";ctx.beginPath();ctx.arc(-w/2+78,-h/2+64,20,0,7);ctx.fill();
  ctx.beginPath();ctx.ellipse(-w/2+78,-h/2+134,40,32,0,Math.PI,0);ctx.fill();
  ctx.fillStyle="rgba(255,255,255,.6)";rr(ctx,-w/2+150,-h/2+46,150,12,6);ctx.fill();rr(ctx,-w/2+150,-h/2+68,100,12,6);ctx.fill();
  ctx.fillStyle="#24242B";rr(ctx,-w/2+20,-h/2+152,250,13,6.5);ctx.fill();rr(ctx,-w/2+20,-h/2+174,170,13,6.5);ctx.fill();
  ctx.fillStyle="#E7E7EC";rr(ctx,-w/2+20,-h/2+198,300,9,4.5);ctx.fill();
  txt(DOMAINS[v%DOMAINS.length],-w/2+20,h/2-16,{size:13,color:"#8E8E98"});
  ctx.fillStyle=`hsl(${hue} 70% 62%)`;rr(ctx,w/2-96,h/2-36,76,24,12);ctx.fill();
  ctx.restore();
}
function pill(x,y,text,{color=INK,dot=null,size=20,bg="#fff",border="#E6E6EE",weight=500,align="center",shadow=true}={}){
  ctx.save();ctx.font=`${weight} ${size}px "Geist"`;const tw=ctx.measureText(text).width;const pad=size*0.9,dw=dot?size*1.1:0;const w=tw+pad*2+dw,h=size*2.1;
  const x0=align==="center"?x-w/2:align==="right"?x-w:x;
  if(shadow){ctx.shadowColor="rgba(30,30,70,.08)";ctx.shadowBlur=24;ctx.shadowOffsetY=8}ctx.fillStyle=bg;rr(ctx,x0,y-h/2,w,h,h/2);ctx.fill();ctx.shadowColor="transparent";
  ctx.strokeStyle=border;ctx.lineWidth=1.2;ctx.stroke();
  if(dot){ctx.fillStyle=dot;ctx.beginPath();ctx.arc(x0+pad+size*0.3,y,size*0.3,0,7);ctx.fill()}
  txt(text,x0+pad+dw,y+1,{size,weight,color,base:"middle"});ctx.restore();return w;
}
function qpts(x1,y1,x2,y2,b,steps=30){const mx=(x1+x2)/2,my=(y1+y2)/2,dx=x2-x1,dy=y2-y1,qx=mx-dy*b,qy=my+dx*b,p=[];for(let i=0;i<=steps;i++){const u=i/steps;p.push([(1-u)*(1-u)*x1+2*(1-u)*u*qx+u*u*x2,(1-u)*(1-u)*y1+2*(1-u)*u*qy+u*u*y2])}return p}
function stroke(p){ctx.beginPath();ctx.moveTo(p[0][0],p[0][1]);for(const q of p.slice(1))ctx.lineTo(q[0],q[1]);ctx.stroke()}

function graph(cx,cy,s,{labels=true,reject=true,newOne=false,seed=11}={}){
  const R=rng(seed);const CL={A:{c:[-460,30],n:10,label:"Kampania A"},B:{c:[0,-40],n:8,label:"Kampania B"},C:{c:[460,60],n:7,label:"Kampania C"}};
  const nodes=[];for(const [k,cl] of Object.entries(CL))for(let i=0;i<cl.n;i++){const a=i*2.39996,r=i?42*Math.sqrt(i):0;nodes.push({camp:k,x:cx+(cl.c[0]+Math.cos(a)*r*1.1)*s,y:cy+(cl.c[1]+Math.sin(a)*r)*s})}
  const noise=[{x:cx-200*s,y:cy+300*s},{x:cx+700*s,y:cy-200*s}];
  const edges=[];for(const k of Object.keys(CL)){const g=nodes.filter(n=>n.camp===k);for(let i=1;i<g.length;i++)edges.push([g[i],g[Math.floor(R()*i)],.4+R()*.6]);for(let x=0;x<Math.floor(g.length*.4);x++){const i=Math.floor(R()*g.length),j=Math.floor(R()*g.length);if(i!==j)edges.push([g[i],g[j],.3+R()*.4])}}
  for(const k of Object.keys(CL)){const g=nodes.filter(n=>n.camp===k);const mx=g.reduce((a,n)=>a+n.x,0)/g.length,my=g.reduce((a,n)=>a+n.y,0)/g.length;const r=Math.max(...g.map(n=>Math.hypot(n.x-mx,n.y-my)))+70*s;
    const gr=ctx.createRadialGradient(mx,my,0,mx,my,r);gr.addColorStop(0,hexA(CAMPC[k],.18));gr.addColorStop(.7,hexA(CAMPC[k],.08));gr.addColorStop(1,hexA(CAMPC[k],0));ctx.fillStyle=gr;ctx.beginPath();ctx.arc(mx,my,r,0,7);ctx.fill();
    if(newOne&&k==="B"){ctx.strokeStyle=hexA(ACC,.45);ctx.lineWidth=2;ctx.beginPath();ctx.arc(mx,my,r*.82,0,7);ctx.stroke()}
    if(labels){txt(CL[k].label,mx,my+r*.82+38*s,{size:24*s,weight:600,align:"center",ls:-.5*s});txt(`${CL[k].n+(newOne&&k==="B"?1:0)} materiałów`,mx,my+r*.82+64*s,{size:16*s,color:MUTED,align:"center"})}}
  ctx.lineCap="round";for(const [a,b,w] of edges){ctx.strokeStyle=hexA(INK,.27);ctx.lineWidth=(1+w*2.4)*s;stroke(qpts(a.x,a.y,b.x,b.y,.08))}
  if(reject){const a=noise[0],b=nodes.find(n=>n.camp==="A");const p=qpts(a.x,a.y,b.x,b.y,.1);ctx.save();ctx.strokeStyle="#C3C3CC";ctx.lineWidth=2*s;ctx.setLineDash([5*s,8*s]);stroke(p);ctx.restore();const m=p[15];ctx.fillStyle="#fff";ctx.beginPath();ctx.arc(m[0],m[1],14*s,0,7);ctx.fill();ctx.strokeStyle="#9A9AA6";ctx.lineWidth=2.4*s;ctx.beginPath();ctx.moveTo(m[0]-6*s,m[1]-6*s);ctx.lineTo(m[0]+6*s,m[1]+6*s);ctx.moveTo(m[0]+6*s,m[1]-6*s);ctx.lineTo(m[0]-6*s,m[1]+6*s);ctx.stroke()}
  if(newOne){const np={x:cx+125*s,y:cy-150*s};nodes.filter(n=>n.camp==="B").sort((p,q)=>Math.hypot(p.x-np.x,p.y-np.y)-Math.hypot(q.x-np.x,q.y-np.y)).slice(0,3).forEach((m,i)=>{ctx.strokeStyle=hexA(ACC,1-i*.2);ctx.lineWidth=(3.2-i*.6)*s;stroke(qpts(np.x,np.y,m.x,m.y,.08))});ctx.save();ctx.fillStyle=ACC;ctx.shadowColor=hexA(ACC,.5);ctx.shadowBlur=20*s;ctx.beginPath();ctx.arc(np.x,np.y,10*s,0,7);ctx.fill();ctx.restore()}
  for(const n of nodes){ctx.fillStyle=INK;ctx.beginPath();ctx.arc(n.x,n.y,8.5*s,0,7);ctx.fill()}
  for(const n of noise){ctx.fillStyle="#B9B9C2";ctx.beginPath();ctx.arc(n.x,n.y,8.5*s,0,7);ctx.fill()}
}

const G=LOGO_GEOMETRY;const LP={front:new Path2D(G.front),back:new Path2D(G.back),hull:new Path2D(G.hull),imic:new Path2D(G.imic)};
function logoW(S){return(G.right-G.left)*S}
function logo(lx,y0,S,{color=INK,accent=ACC,mOnly=false}={}){const x0=lx-G.left*S;
  const cw=ctx.canvas.width,ch=ctx.canvas.height;const off=document.createElement("canvas");off.width=cw;off.height=ch;const o=off.getContext("2d");
  o.setTransform(S,0,0,S,x0,y0);o.fillStyle=accent;o.fill(LP.back);o.globalCompositeOperation="destination-out";o.strokeStyle="#000";o.lineWidth=G.knock;o.lineJoin="round";o.fill(LP.hull);o.stroke(LP.hull);
  ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.drawImage(off,0,0);ctx.restore();
  ctx.save();ctx.translate(x0,y0);ctx.scale(S,S);ctx.fillStyle=color;ctx.fill(LP.front);if(!mOnly)ctx.fill(LP.imic);ctx.restore();
}
function copies(cx,cy,s,{n=3,step=48,gap=9,bg="#FFFFFF"}={}){
  for(let i=n;i>=1;i--){const x=cx-step*i*s,y=cy-step*i*s;ctx.save();ctx.fillStyle=hexA(ACC,[.62,.34,.16,.08][i-1]);rr(ctx,x-180*s,y-125*s,360*s,250*s,26*s);ctx.fill();ctx.restore()}
  ctx.save();ctx.fillStyle=bg;rr(ctx,cx-180*s-gap*s,cy-125*s-gap*s,360*s+2*gap*s,250*s+2*gap*s,(26+gap)*s);ctx.fill();ctx.restore();
  ctx.save();ctx.beginPath();ctx.rect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.restore();
  card(cx,cy,s,0,1);
}

async function fonts(){await Promise.all(['400 40px "Geist"','500 40px "Geist"','600 40px "Geist"'].map(f=>document.fonts.load(f)))}

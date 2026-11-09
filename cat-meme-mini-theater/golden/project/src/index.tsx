import React from 'react';
import {AbsoluteFill,Audio,Composition,Img,interpolate,registerRoot,spring,staticFile,useCurrentFrame} from 'remotion';
import assets from './assets.json';
import './style.css';

const FPS=30;
type CatName=keyof typeof assets;
const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
const beats=[
  {from:0,to:150,title:'下班前一分钟',time:'17:59',chapter:'01 / 准点下班计划',bg:'office-wide.jpeg'},
  {from:150,to:300,title:'一个小小的需求',time:'17:59',chapter:'02 / 消息来了',bg:'office-desk.jpeg'},
  {from:300,to:420,title:'我的理解',time:'17:59',chapter:'03 / 内心小剧场',bg:'office-wide.jpeg'},
  {from:420,to:570,title:'老板的理解',time:'18:00',chapter:'04 / 需求对齐',bg:'office-desk.jpeg'},
  {from:570,to:660,title:'对齐失败',time:'18:00',chapter:'05 / 内心小剧场',bg:'office-wide.jpeg'},
  {from:660,to:810,title:'同事的温馨提醒',time:'18:01',chapter:'06 / 过来人',bg:'office-wide.jpeg'},
  {from:810,to:960,title:'这就叫微调',time:'加班中',chapter:'07 / 一点点改动',bg:'office-blue.jpeg'},
  {from:960,to:1110,title:'终于，改完了',time:'23:59',chapter:'08 / 内心小剧场',bg:'office-blue.jpeg'},
  {from:1110,to:1200,title:'第二天',time:'08:59',chapter:'09 / 循环开始',bg:'office-wide.jpeg'},
];

function Cat({name,x,y,height,frame,flip=false,freeze=false,style={}}:{name:CatName;x:number;y:number;height:number;frame:number;flip?:boolean;freeze?:boolean;style?:React.CSSProperties}){
  const m=assets[name]; const n=freeze?Math.min(15,m.frames-1):((Math.max(0,Math.floor(frame))%m.frames));
  return <Img src={staticFile(`assets/${name}/${String(n).padStart(4,'0')}.png`)} style={{position:'absolute',left:x,top:y,height,width:height*m.width/m.height,objectFit:'contain',transform:flip?'scaleX(-1)':undefined,filter:'drop-shadow(0px 16px 8px rgba(0,0,0,.3))',...style}}/>;
}
function Pill({children,style={}}:{children:React.ReactNode;style?:React.CSSProperties}){return <div className="pill" style={style}>{children}</div>}
function Caption({speaker,children,accent=false}:{speaker:string;children:React.ReactNode;accent?:boolean}){return <div className="caption"><span className="speaker" style={{background:accent?'#ff745b':'#d6fa68'}}>{speaker}</span><span>{children}</span></div>}
function Bubble({children,x,y,width=620,enter=0,frame,color='#fff8e9'}:{children:React.ReactNode;x:number;y:number;width?:number;enter?:number;frame:number;color?:string}){
  const s=spring({frame:Math.max(0,frame-enter),fps:FPS,config:{damping:17,stiffness:160}});
  if(frame<enter)return null;
  return <div className="bubble" style={{left:x,top:y,width,background:color,opacity:Math.min(1,s*2),transform:`translateY(${(1-s)*25}px) scale(${.94+s*.06})`}}>{children}<div className="tail" style={{borderTopColor:color}}/></div>
}
function Film(){
  const frame=useCurrentFrame();const shot=beats.find(b=>frame>=b.from&&frame<b.to)!;
  const f=frame-shot.from;const index=beats.indexOf(shot);const night=index===6||index===7;
  const zoom=1+f*.00012;
  const shake=index===4&&f<14?Math.sin(f*2.4)*(14-f)*1.3:0;
  const time=index===6?['18:01','19:36','21:08','22:47','23:59'][Math.min(4,Math.floor(f/30))]:shot.time;
  return <AbsoluteFill className="film">
    <Audio src={staticFile('assets/soundtrack.wav')}/>
    <AbsoluteFill style={{transform:`translateX(${shake}px)`}}>
      <Img src={staticFile(`source/backgrounds/${shot.bg}`)} style={{position:'absolute',width:'100%',height:'100%',objectFit:'cover',transform:`scale(${zoom})`,filter:night?'brightness(.36) saturate(.65) hue-rotate(8deg)':'brightness(.72) saturate(.82)'}}/>
      <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(7,19,24,.55),transparent 32%,transparent 65%,rgba(7,19,24,.94))'}}/>
      {night&&<AbsoluteFill style={{background:'radial-gradient(ellipse at 32% 55%,rgba(90,163,235,.28),transparent 60%)'}}/>}
      <div className="topline"><div className="brand"><span className="brand-dot"/> 猫班日记 <span className="episode">EP. 01</span></div><div className="chapter">{shot.chapter}</div></div>
      <div className="clock"><div className="clock-label">{index===8?'NEXT DAY':'OFFICE TIME'}</div><div>{time}</div></div>
      {index===0&&<>
        <div className="opening-title"><div className="eyebrow">一个关于「微调」的故事</div><div>下班前<span>一分钟</span></div><div className="subtitle">打工猫的愿望，通常很简单。</div></div>
        <Cat name="typing" x={1070} y={390} height={440} frame={f}/>
        <Pill style={{left:1150,top:300}}>✓ 今日工作：已完成</Pill>
        <Caption speaker="我">今天，谁也别想阻止我准点下班。</Caption>
      </>}
      {index===1&&<>
        <Cat name="typing" x={150} y={440} height={390} frame={150+f}/>
        <Cat name="boss" x={1330} y={320} height={540} frame={f+12}/>
        <Pill style={{left:1410,top:240,background:'#ffc9aa'}}>老板</Pill>
        <Bubble x={660} y={270} width={590} frame={f} enter={10}>在吗？<br/><strong>有个小改动。</strong></Bubble>
        {f>70&&<Pill style={{left:300,top:330}}>……现在？</Pill>}
        <Caption speaker="老板" accent>不耽误你下班，就改一点点。</Caption>
      </>}
      {index===2&&<>
        <div className="thought-label">我的脑内翻译</div>
        <Cat name="confused" x={300} y={300} height={550} frame={f}/>
        <div className="interpretation"><div className="small">所谓「小改动」</div><div>改个标点？</div><div className="estimate">预计耗时 <b>30 秒</b></div></div>
        <Caption speaker="内心">改一个字对吧？那没问题。</Caption>
      </>}
      {index===3&&<>
        <Cat name="boss" x={1300} y={300} height={560} frame={f+105}/>
        <div className="request-board"><div className="board-heading">本次修改范围 <span>“一点点”</span></div>
          {['整体风格换一下','逻辑重新梳理一下','顺便，全部重做一下'].map((s,i)=><div key={s} className="request" style={{opacity:interpolate(f,[i*27+6,i*27+14],[0,1],clamp),transform:`translateX(${interpolate(f,[i*27+6,i*27+14],[25,0],clamp)}px)`}}><span>0{i+1}</span>{s}</div>)}
        </div>
        <Caption speaker="老板" accent>{f<65?'很简单，整体感觉再调整一下。':'其他都挺好的。就是全部重做一下。'}</Caption>
      </>}
      {index===4&&<>
        <AbsoluteFill style={{background:'rgba(13,22,27,.52)'}}/>
        <div className="shock-word" style={{transform:`scale(${interpolate(f,[0,10,89],[.8,1,1.04],clamp)})`}}>重 做 ？</div>
        <Cat name="shocked" x={800} y={280} height={600} frame={f} style={{transform:`scale(${interpolate(f,[0,70],[1,1.12],clamp)})`,transformOrigin:'bottom'}}/>
        <Pill style={{left:130,top:330,background:'#ff745b',transform:'rotate(-8deg)'}}>CPU 已停止工作</Pill>
        <Caption speaker="内心">你管这个……叫微调？</Caption>
      </>}
      {index===5&&<>
        <Cat name="laughing" x={220} y={280} height={580} frame={f}/>
        <Bubble x={1000} y={310} width={680} frame={f} enter={8}>他说「一点点」，<br/>你怎么还<strong>当真了？</strong></Bubble>
        <Pill style={{left:370,top:205}}>隔壁工位 · 过来猫</Pill>
        <Caption speaker="同事">上次他说「五分钟」，我过了个夜。</Caption>
      </>}
      {index===6&&<>
        <Cat name="typing" x={235} y={360} height={480} frame={f*1.6}/>
        <div className="version-card"><div className="small">保存文件</div><div>最终版{['','_真的','_真不改了','_打死不改','_老板说再改'][Math.min(4,Math.floor(f/30))]}.pptx</div><div className="progress-track"><div style={{width:`${35+(f%30)*2}%`}}/></div><span>正在重新定义「最终」…</span></div>
        <Img src={staticFile('source/props/coffee.png')} style={{position:'absolute',left:1040,top:650,width:180}}/>
        <Caption speaker="我">好的。收到。马上。没问题。</Caption>
      </>}
      {index===7&&<>
        <Cat name="sad" x={230} y={210} height={650} frame={f}/>
        <div className="ending-line"><div className="small">23:59 · 第 18 次保存</div><div>明天，<br/><span>一定准点走。</span></div></div>
        <Caption speaker="内心">人可以加班，梦想不能下班。</Caption>
      </>}
      {index===8&&<>
        <Cat name="typing" x={210} y={400} height={430} frame={f} freeze/>
        <Bubble x={910} y={295} width={710} frame={f} enter={6}>早！昨晚我又想了一下。<br/><strong>还是第一版好。</strong></Bubble>
        <Pill style={{left:1070,top:220,background:'#ffc9aa'}}>老板 · 新消息</Pill>
        {f>29&&<div className="end-stamp" style={{opacity:interpolate(f,[30,39],[0,1],clamp)}}>明天一定™</div>}
        {f>=24&&<Caption speaker="我">……</Caption>}
      </>}
      <div className="bottom-meta"><span>下班前一分钟</span><span>{String(index+1).padStart(2,'0')} / 09</span></div>
      <div className="timeline" style={{width:`${frame/1199*100}%`}}/>
    </AbsoluteFill>
  </AbsoluteFill>;
}
const Root=()=> <Composition id="ClockOut" component={Film} width={1920} height={1080} fps={FPS} durationInFrames={1200}/>;
registerRoot(Root);

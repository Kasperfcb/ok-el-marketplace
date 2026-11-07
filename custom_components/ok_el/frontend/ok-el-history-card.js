/* OK El history dashboard for Home Assistant.
 * Only uses authenticated hass.callWS; no network calls to third parties.
 */
"use strict";
class OKElHistoryCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this._config={};
    this._hass=null;
    this._period="DAY";
    this._metric="kwh";
    this._limit="30";
    this._rows=[];
    this._coverage={};
    this._busy=false;
    this._loading=false;
    this._lastFetch=0;
    this._error="";
    this._timer=null;
    this._setup=false;
  }

  static getStubConfig() {return {type:"custom:ok-el-history-card"};}
  getCardSize() {return 7;}
  setConfig(config) {
    if(!config || config.type!=="custom:ok-el-history-card") {
      throw new Error("Brug type: custom:ok-el-history-card");
    }
    this._config=config;
  }
  set hass(hass) {
    this._hass=hass;
    if(this.isConnected && !this._loading && Date.now()-this._lastFetch>90000) {
      this._fetch();
    }
  }
  connectedCallback() {
    this._init();
    this._fetch();
    if(!this._timer) this._timer=setInterval(()=>{if(this._busy || Date.now()-this._lastFetch>30000)this._fetch();},6000);
  }
  disconnectedCallback() {
    if(this._timer) clearInterval(this._timer);
    this._timer=null;
  }

  _init() {
    if(this._setup) return;
    this._setup=true;
    this.shadowRoot.innerHTML=`
      <style>
        :host{display:block;color:var(--primary-text-color,#f0f4fa);font-family:inherit}
        ha-card{padding:20px;background:var(--ha-card-background,var(--card-background-color,#182336));border-radius:16px;display:block}
        header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px;flex-wrap:wrap}
        h2{margin:0;font-size:22px;font-weight:700;letter-spacing:-.3px}
        p{margin:6px 0 0;color:var(--secondary-text-color,#9bacc0);font-size:13px}
        button,select{font:inherit;color:inherit;background:var(--secondary-background-color,#243448);border:1px solid var(--divider-color,#3a4659);border-radius:8px;padding:9px 12px;cursor:pointer}
        button:focus-visible,select:focus-visible{outline:2px solid var(--primary-color,#57bfb2);outline-offset:2px}
        button[disabled]{opacity:.5;cursor:wait}
        button.active{background:var(--primary-color,#398b81);color:var(--text-primary-color,#fff);border-color:var(--primary-color,#398b81)}
        .tabs,.controls,.archive-controls{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
        .tabs{margin-bottom:16px}
        .tabs button{flex:1;min-width:68px}
        .cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:18px}
        .stat{border:1px solid var(--divider-color,#3a4659);border-radius:11px;padding:16px;background:var(--secondary-background-color,#1f2c40)}
        .stat small{display:block;font-size:12px;color:var(--secondary-text-color,#9bacc0);margin-bottom:9px}
        .stat strong{font-size:clamp(16px,2.5vw,26px);font-weight:700;overflow-wrap:anywhere}
        .chartbox{border:1px solid var(--divider-color,#3a4659);border-radius:11px;padding:13px;margin-top:12px}
        .chartbox svg{width:100%;min-height:180px;display:block}
        .chartarea{position:relative;min-height:180px}
        .graphtip{position:absolute;z-index:5;min-width:190px;max-width:260px;padding:12px 14px;
          border:1px solid var(--divider-color,#426079);border-radius:11px;
          background:var(--ha-card-background,var(--card-background-color,#152334));
          color:var(--primary-text-color,#f5f8ff);box-shadow:0 8px 25px rgba(0,0,0,.38);
          pointer-events:none;font-variant-numeric:tabular-nums}
        .graphtip[hidden]{display:none}
        .graphtip strong{display:block;font-size:13px;margin-bottom:8px}
        .graphtip .tiprow{display:flex;justify-content:space-between;gap:20px;font-size:13px;line-height:1.85}
        .graphtip .tiprow span{color:var(--secondary-text-color,#b9c7d5)}
        .graphtip .tiprow b{white-space:nowrap}
        .chartarea svg rect:focus-visible{stroke:var(--primary-text-color,#fff);stroke-width:2}

        .charthead{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
        .tablewrap{margin-top:16px;max-height:340px;overflow:auto}
        table{border-collapse:collapse;width:100%;font-size:13px}
        thead th{text-align:left;position:sticky;top:0;background:var(--ha-card-background,var(--card-background-color,#182336));padding:10px 9px;border-bottom:1px solid var(--divider-color,#3a4659)}
        tbody td{padding:10px 9px;border-bottom:1px solid var(--divider-color,#3a4659)}
        td.num,th.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
        .muted{color:var(--secondary-text-color,#98aac3)}
        .archive{border-top:1px solid var(--divider-color,#3a4659);margin-top:18px;padding-top:17px}
        .status{font-size:12px;color:var(--secondary-text-color,#98aac3);line-height:1.5;margin:10px 0}
        .error{color:var(--error-color,#f28b82)}
        .busy{color:var(--warning-color,#ffc676)}
        .notice{font-size:11px;line-height:1.6;color:var(--secondary-text-color,#98aac3);margin-top:12px}
        @media(max-width:600px){ha-card{padding:14px}.cards{grid-template-columns:1fr}.tabs button{min-width:58px;padding:8px 6px}}
      </style>
      <ha-card>
        <header><div><h2>OK El · Historik</h2><p>Dit faktiske forbrug og dine elpriser</p></div>
          <button id="reload" aria-label="Opdater historik">↻ Opdater visning</button>
        </header>
        <div class="tabs" id="tabs">
          <button data-period="HOUR">Timer</button><button data-period="DAY">Dage</button>
          <button data-period="MONTH">Måneder</button><button data-period="QUARTER">Kvartaler</button>
          <button data-period="YEAR">År</button>
        </div>
        <div class="cards">
          <div class="stat"><small>Registreret forbrug</small><strong id="sumkwh">—</strong></div>
          <div class="stat"><small>Registreret pris inkl. moms</small><strong id="sumcost">—</strong></div>
          <div class="stat"><small>Registrerede intervaller</small><strong id="points">—</strong></div>
        </div>
        <div class="chartbox">
          <div class="charthead">
            <strong>Forbrug over tid</strong>
            <div class="controls">
              <button data-metric="kwh">kWh</button>
              <button data-metric="dkk_inkl_moms">Kroner</button>
              <select id="limit" aria-label="Antal perioder">
                <option value="7">Seneste 7</option><option value="30" selected>Seneste 30</option>
                <option value="90">Seneste 90</option><option value="365">Seneste 365</option>
                <option value="all">Alle</option>
              </select>
            </div>
          </div>
          <div class="chartarea" id="chartarea">
            <svg id="chart" viewBox="0 0 900 260" role="img" aria-label="Graf over elforbrug"></svg>
            <div id="tooltip" class="graphtip" role="status" hidden>
              <strong id="tipdate">—</strong>
              <div class="tiprow"><span>Elforbrug</span><b id="tipkwh">—</b></div>
              <div class="tiprow"><span>Pris inkl. moms</span><b id="tipcost">—</b></div>
              <div class="tiprow"><span>Pris pr. kWh</span><b id="tipunit">—</b></div>
            </div>
          </div>
        </div>
        <div class="tablewrap"><table><thead><tr><th>Dato og periode</th><th class="num">kWh</th>
          <th class="num">Kr. inkl. moms</th><th class="num">Kr./kWh</th></tr></thead>
          <tbody id="entries"></tbody></table></div>
        <div class="archive">
          <strong>Hent mere historik fra Min OK</strong>
          <p class="muted">Historikken gemmes privat i Home Assistant og hentes kun efter dit valg.</p>
          <div class="archive-controls">
            <label>Dagsdata <select id="months"><option value="6">6 måneder</option><option value="12" selected>12 måneder</option><option value="24">24 måneder</option><option value="36">36 måneder</option></select></label>
            <label>Timedata <select id="hours"><option value="0">Ingen</option><option value="7" selected>7 dage</option><option value="14">14 dage</option><option value="30">30 dage</option></select></label>
            <button id="import">Hent historik</button>
          </div>
          <div id="status" class="status">Forbereder historik…</div>
        </div>
        <div class="notice">Aflæsninger kan være forsinkede. Manglende værdier vises som — og tælles ikke som 0 kWh. Registrerede beløb kan afvige fra den endelige faktura. Timehistorik hentes kun for faktisk aflæste dage.</div>
      </ha-card>`;
    this.shadowRoot.querySelectorAll("[data-period]").forEach(button=>
      button.addEventListener("click",()=>{
        this._period=button.dataset.period;
        this._limit=["HOUR","DAY"].includes(this._period)?"30":"all";
        this.shadowRoot.getElementById("limit").value=this._limit;
        this._fetch();
      }));
    this.shadowRoot.querySelectorAll("[data-metric]").forEach(button=>
      button.addEventListener("click",()=>{
        this._metric=button.dataset.metric;this._render();
      }));
    this.shadowRoot.getElementById("limit").addEventListener("change",event=>{
      this._limit=event.target.value;this._render();
    });
    this.shadowRoot.getElementById("reload").addEventListener("click",()=>this._fetch());
    this.shadowRoot.getElementById("import").addEventListener("click",()=>this._import());
  }
  async _fetch() {
    if(!this._hass || this._loading || !this.isConnected)return;
    this._loading=true;
    try{
      const q={type:"ok_el/history",period:this._period};
      if(this._config.entry_id)q.entry_id=this._config.entry_id;
      const result=await this._hass.callWS(q);
      this._rows=Array.isArray(result.rows)?result.rows:[];
      this._coverage=result.coverage||{};
      this._busy=!!result.busy;
      this._progress=result.progress||{};
      this._error=result.last_error||"";
      this._lastCompleted=result.last_completed||"";
      this._lastFetch=Date.now();
      this._render();
    }catch(error){
      this._error="Kunne ikke hente historik. Kontrollér integrationen og dine brugerrettigheder.";
      this._renderStatus();
    }finally{this._loading=false;}
  }
  async _import() {
    if(!this._hass||this._busy)return;
    const months=Number(this.shadowRoot.getElementById("months").value);
    const hour_days=Number(this.shadowRoot.getElementById("hours").value);
    const q={type:"ok_el/backfill",months,hour_days};
    if(this._config.entry_id)q.entry_id=this._config.entry_id;
    try {
      const result=await this._hass.callWS(q);
      this._busy=!!result.busy;
      this._progress={completed:0,total:0,stage:"Starter historikimport..."};
      this._error="";
      this._renderStatus();
    }catch(e){
      this._error="Kunne ikke starte historikimport. Admin-rettigheder kan være påkrævet.";
      this._renderStatus();
    }
  }
  _num(v){return typeof v==="number"&&Number.isFinite(v);}
  _fmt(v,decimals=2){return this._num(v)?new Intl.NumberFormat("da-DK",{minimumFractionDigits:decimals,maximumFractionDigits:decimals}).format(v):"—";}
  _date(v) {
    const text=String(v||"");
    const iso=text.slice(0,10);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(iso))return text;
    const d=new Date(iso+"T12:00:00Z");
    const label=new Intl.DateTimeFormat("da-DK",{weekday:"long",day:"2-digit",month:"2-digit",year:"numeric",timeZone:"Europe/Copenhagen"}).format(d);
    if(this._period==="HOUR")return label+" · "+text.slice(11,16);
    if(this._period==="MONTH")return iso.slice(0,7);
    if(this._period==="QUARTER")return "K"+Math.ceil(Number(iso.slice(5,7))/3)+" "+iso.slice(0,4);
    if(this._period==="YEAR")return iso.slice(0,4);
    return label.charAt(0).toUpperCase()+label.slice(1);
  }
  _svg(tag,attrs={},text) {
    const el=document.createElementNS("http://www.w3.org/2000/svg",tag);
    for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));
    if(text!==undefined)el.textContent=String(text);
    return el;
  }
  _hideTooltip() {
    const tooltip=this.shadowRoot.getElementById("tooltip");
    if(tooltip)tooltip.hidden=true;
  }
  _showTooltip(row,event,target) {
    const root=this.shadowRoot;
    const tooltip=root.getElementById("tooltip");
    if(!tooltip)return;
    root.getElementById("tipdate").textContent=this._date(row.dato);
    root.getElementById("tipkwh").textContent=this._fmt(row.kwh)+" kWh";
    root.getElementById("tipcost").textContent=this._fmt(row.dkk_inkl_moms)+" kr.";
    root.getElementById("tipunit").textContent=this._fmt(row.dkk_pr_kwh_inkl_moms,3)+" kr./kWh";
    tooltip.hidden=false;
    const area=root.getElementById("chartarea").getBoundingClientRect();
    const spot=target.getBoundingClientRect();
    const x=typeof event.clientX==="number"&&event.clientX>0?event.clientX:spot.left+spot.width/2;
    const y=typeof event.clientY==="number"&&event.clientY>0?event.clientY:spot.top+spot.height/2;
    const box=tooltip.getBoundingClientRect();
    tooltip.style.left=Math.max(4,Math.min(x-area.left+12,area.width-box.width-4))+"px";
    tooltip.style.top=Math.max(4,Math.min(y-area.top-box.height-10,area.height-box.height-4))+"px";
  }
  _chart(rows) {
    const svg=this.shadowRoot.getElementById("chart");
    svg.replaceChildren();
    this._hideTooltip();
    const data=rows.filter(r=>this._num(r[this._metric]));
    if(!data.length){
      svg.appendChild(this._svg("text",{x:450,y:132,fill:"currentColor",opacity:".65","text-anchor":"middle","font-size":16},"Ingen aflæste data for den valgte periode"));
      return;
    }
    const max=Math.max(...data.map(r=>r[this._metric]),.1),left=68,top=20,w=810,h=190;
    for(let k=0;k<5;k++){
      const y=top+h-k*h/4;
      svg.appendChild(this._svg("line",{x1:left,x2:left+w,y1:y,y2:y,stroke:"currentColor",opacity:".15"}));
      svg.appendChild(this._svg("text",{x:left-12,y:y+4,fill:"currentColor",opacity:".65","font-size":11,"text-anchor":"end"},this._fmt(max*k/4,1)));
    }
    const cell=w/Math.max(rows.length,1),gap=Math.min(4,cell*.2);
    rows.forEach((r,i)=>{
      const value=r[this._metric];if(!this._num(value))return;
      const height=Math.max(1,value/max*h);
      const rect=this._svg("rect",{x:left+i*cell+gap/2,y:top+h-height,width:Math.max(.5,cell-gap),height,rx:Math.min(3,cell/5),fill:this._metric==="kwh"?"#45cbb6":"#77aaff"});
      svg.appendChild(rect);
      const hit=this._svg("rect",{
        x:left+i*cell,y:top,width:Math.max(.5,cell),height:h,
        fill:"transparent",tabindex:0,role:"button",
        "aria-label":this._date(r.dato)+", "+this._fmt(r.kwh)+" kilowatt-timer, "+
          this._fmt(r.dkk_inkl_moms)+" kroner"
      });
      hit.style.cursor="crosshair";
      hit.addEventListener("pointerenter",event=>this._showTooltip(r,event,hit));
      hit.addEventListener("pointermove",event=>this._showTooltip(r,event,hit));
      hit.addEventListener("focus",event=>this._showTooltip(r,event,hit));
      hit.addEventListener("blur",()=>this._hideTooltip());
      hit.addEventListener("click",event=>this._showTooltip(r,event,hit));
      svg.appendChild(hit);
    });
    svg.addEventListener("pointerleave",()=>this._hideTooltip(),{once:true});
    const marks=Math.min(6,rows.length);
    for(let i=0;i<marks;i++){
      const index=marks===1?0:Math.round((rows.length-1)*i/(marks-1));
      const date=String(rows[index].dato||"").slice(5,10);
      svg.appendChild(this._svg("text",{x:left+(index+.5)*cell,y:238,"text-anchor":"middle","font-size":11,fill:"currentColor",opacity:".7"},date));
    }
  }
  _renderStatus() {
    const status=this.shadowRoot.getElementById("status");
    if(!status)return;
    const pieces=Object.entries(this._coverage).map(([k,v])=>k+": "+v).join(" · ");
    const p=this._progress||{};
    const stage=typeof p.stage==="string"?p.stage:"";
    const pct=p.total>0?Math.min(100,Math.round(100*p.completed/p.total)):0;
    const progress=this._busy?(
      "Henter historik: "+(p.total>0?p.completed+"/"+p.total+" trin ("+pct+"%). ":"")+
      (stage||"Starter…")+". "
    ):stage?stage+". ":"";
    status.textContent=progress+
      (this._error?this._error+" ":"")+
      "Lokalt gemt: "+(pieces||"ingen data endnu")+
      (this._lastCompleted?" · Sidste import: "+this._lastCompleted:"");
    status.className="status"+(this._error?" error":this._busy?" busy":"");
    this.shadowRoot.getElementById("import").disabled=this._busy;
  }
  _render() {
    if(!this._setup)return;
    this.shadowRoot.querySelectorAll("[data-period]").forEach(el=>el.classList.toggle("active",el.dataset.period===this._period));
    this.shadowRoot.querySelectorAll("[data-metric]").forEach(el=>el.classList.toggle("active",el.dataset.metric===this._metric));
    const sorted=[...this._rows].sort((a,b)=>String(a.dato||"").localeCompare(String(b.dato||"")));
    const rows=this._limit==="all"?sorted:sorted.slice(-Number(this._limit));
    const measured=rows.filter(r=>this._num(r.kwh));
    const priced=rows.filter(r=>this._num(r.dkk_inkl_moms));
    const total=(data,k)=>data.reduce((sum,row)=>sum+row[k],0);
    this.shadowRoot.getElementById("sumkwh").textContent=measured.length?this._fmt(total(measured,"kwh"))+" kWh":"—";
    this.shadowRoot.getElementById("sumcost").textContent=priced.length?this._fmt(total(priced,"dkk_inkl_moms"))+" kr.":"—";
    this.shadowRoot.getElementById("points").textContent=measured.length+" / "+rows.length;
    this._chart(rows);
    const tbody=this.shadowRoot.getElementById("entries");tbody.replaceChildren();
    for(const r of rows.slice().reverse()){
      const tr=document.createElement("tr");
      for(const [i,v] of [this._date(r.dato),this._fmt(r.kwh),this._fmt(r.dkk_inkl_moms),this._fmt(r.dkk_pr_kwh_inkl_moms,3)].entries()){
        const td=document.createElement("td");td.textContent=v;
        if(i)td.className="num";tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    if(!rows.length){
      const tr=document.createElement("tr"),td=document.createElement("td");
      td.colSpan=4;td.textContent="Der er endnu ingen historik. Brug Hent historik nedenfor.";
      tr.appendChild(td);tbody.appendChild(tr);
    }
    this._renderStatus();
  }
}
if(!customElements.get("ok-el-history-card"))customElements.define("ok-el-history-card",OKElHistoryCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(card=>card.type==="ok-el-history-card")){
  window.customCards.push({
    type:"ok-el-history-card",
    name:"OK El – Historik",
    description:"Grafer, time-, dag-, måneds-, kvartals- og årsdata fra din private OK El-integration",
    preview:false
  });
}

"""Render the study and a local, searchable all-party candidate browser."""

import html
import json
import re


def inline(text):
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", text)


def article(markdown):
    blocks, table, listing = [], False, False
    for line in markdown.splitlines():
        if not line.startswith("|") and table:
            blocks.append("</tbody></table></div>")
            table = False
        if not line.startswith("- ") and listing:
            blocks.append("</ul>")
            listing = False
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            blocks.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r"[-: ]+", cell) for cell in cells):
                continue
            tag = "td" if table else "th"
            if not table:
                blocks.append('<div class="table-wrap"><table><thead>')
            blocks.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            if not table:
                blocks.append("</thead><tbody>")
                table = True
        elif line.startswith("- "):
            if not listing:
                blocks.append("<ul>")
                listing = True
            blocks.append(f"<li>{inline(line[2:])}</li>")
        elif line:
            blocks.append(f"<p>{inline(line)}</p>")
    if table:
        blocks.append("</tbody></table></div>")
    if listing:
        blocks.append("</ul>")
    return "\n".join(blocks)


STYLE = """
:root{color-scheme:light;--paper:#f7f5f0;--ink:#1a1a1a;--muted:#6b6b6b;--line:#d6d3cc;--accent:#a9432b}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:18px/1.65 Georgia,serif}
main{max-width:1180px;margin:auto;padding:55px 30px 80px}header{max-width:850px;margin-bottom:45px}
.eyebrow{font:13px/1.5 system-ui,sans-serif;letter-spacing:.13em;text-transform:uppercase;color:var(--accent)}
h1{font-size:clamp(34px,5vw,61px);line-height:1.08;letter-spacing:-.025em;margin:20px 0}
.standfirst{font-size:22px;line-height:1.5;color:var(--muted)}nav{display:flex;gap:22px;flex-wrap:wrap}
a{color:var(--accent);text-underline-offset:3px}h2{font-size:30px;line-height:1.25;margin:48px 0 18px}
h3{font-size:23px;margin:12px 0}#findings{max-width:900px}p,li{max-width:830px}li{margin:8px 0}
figure{margin:38px 0 55px;border-top:1px solid var(--line);padding-top:18px}figure img{display:block;width:100%;height:auto}
figcaption,.muted{font-size:15px;line-height:1.6;color:var(--muted)}figcaption{max-width:930px;margin-top:12px}
table{width:100%;border-collapse:collapse;font:14px/1.5 system-ui,sans-serif}
th,td{text-align:left;padding:13px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;white-space:nowrap}td:first-child{min-width:170px}.table-wrap{overflow:auto;max-width:100%}
label{display:flex;flex-direction:column;gap:5px;font:14px/1.5 system-ui,sans-serif}
.filters{display:flex;flex-wrap:wrap;gap:14px;margin:24px 0}input,select,button{font:15px/1.4 system-ui,sans-serif}
input,select{padding:9px 10px;border:1px solid #aaa79f;border-radius:0;background:transparent;color:var(--ink);max-width:100%}
input{width:280px}button{border:1px solid #aaa79f;background:transparent;color:var(--ink);padding:8px 14px;cursor:pointer}
button:disabled{opacity:.45;cursor:default}button.link{border:0;padding:0;color:var(--accent);text-align:left;text-decoration:underline}
.pager{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:20px 0}#profile{border-top:2px solid var(--ink);margin-top:30px;padding:20px 0}
#profile p{white-space:pre-line;overflow-wrap:anywhere}#profile ul{padding-left:22px}
#profile a{overflow-wrap:anywhere}
details{border-top:1px solid var(--line);padding:10px 0}summary{cursor:pointer;font-weight:bold}
#profile pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 system-ui,sans-serif}
.evidence-value{min-width:220px;max-width:420px;white-space:pre-line;overflow-wrap:anywhere}
footer{border-top:1px solid var(--line);margin-top:60px;padding-top:20px}code{font-size:.85em;overflow-wrap:anywhere}
@media(max-width:600px){main{padding:30px 18px 55px}body{font-size:17px}.standfirst{font-size:19px}h2{font-size:26px}
.filters label{flex:1 1 130px}.filters input,.filters select{width:100%}th,td{padding:10px 8px}figure{margin:28px -8px 38px}figcaption{padding:0 8px}}
"""

SCRIPT = """
const electionRows=JSON.parse(document.getElementById('candidate-data').textContent);
const traitRows=JSON.parse(document.getElementById('trait-data').textContent);
const memberRows=JSON.parse(document.getElementById('member-data').textContent);
const participationStates=new Map(JSON.parse(document.getElementById('participation-data').textContent).map(r=>[r.state_context_id,r]));
const $=id=>document.getElementById(id);
function memberProfile(r){return {...r,name:r.name||'Vacant seat',candidate_id:r.candidate_id||null,
 current_House_member:r.congress==='119'?Boolean(r.bioguide_id):Boolean(r.current_seat_id),
 provider_winner_flag:r.congress==='120'&&Boolean(r.name),comparison_eligible:false,comparison_holds:[],
 votes:null,presidential_gap_margin_pp:null,held_out_residual_margin_pp:null,
 incoming_classification:r.entry_classification||null,
 professional_history:r.professional_history||r.reported_prior_background,
 education:r.education||r.wikipedia_education||r.candidate_profile_education,
 background_evidence:[r.biography_evidence,r.religion_evidence,r.reviewed_biography_evidence,r.wikipedia_roster_evidence,r.roster_evidence,r.service_evidence,r.voting_evidence],
 campaign_websites:[],machine_biography_fields_unreviewed:[],acquired_background_observations:[],background_model_ready:false}}
const datasets={candidates:electionRows,current:memberRows.current.map(memberProfile),incoming:memberRows.incoming.map(memberProfile)};
let rows=electionRows,page=0, filtered=rows;
const pageSize=25;
function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n}
function pretty(value){
 if(value===null||value===undefined||value==='')return 'Not qualified / unavailable';
 if(typeof value==='string'){try{return pretty(JSON.parse(value))}catch{return value}}
 if(Array.isArray(value))return value.map(pretty).join('; ');
 if(typeof value==='object')return value.literal||Object.entries(value).map(([k,v])=>k.replaceAll('_',' ')+': '+pretty(v)).join('; ');
 return String(value);
}
function urls(value,found=new Set()){
 if(typeof value==='string'){try{urls(JSON.parse(value),found)}catch{try{const u=new URL(value);if(['https:','http:'].includes(u.protocol))found.add(u.href)}catch{}}}
 else if(Array.isArray(value))value.forEach(v=>urls(v,found));
 else if(value&&typeof value==='object')Object.values(value).forEach(v=>urls(v,found));
 return found;
}
function downloadCSV(records,keys,filename){
 function cell(value){let text=value===null||value===undefined?'':typeof value==='object'?JSON.stringify(value):String(value);if(typeof value==='string'&&/^\\s*[=+@-]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"'}
 const csv=[keys.map(cell).join(','),...records.map(r=>keys.map(k=>cell(r[k])).join(','))].join('\\r\\n')+'\\r\\n';
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=el('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function showEvidence(box,row){
 const observations=row.acquired_background_observations||[];
 box.append(el('h3','Acquired background observations'));
 if(!observations.length){box.append(el('p','No observations in the election-candidate evidence table. Any separately acquired member evidence is shown above. This is not a negative trait label.'));return}
 box.append(el('p',observations.length+' source observations. Values may be historical, overlapping, candidate-reported or unreviewed machine extractions. Read the source, date and qualification; these observations have not been newly added to the models.'));
 const download=el('button','Download these source observations (CSV)');download.type='button';download.id='download-evidence';
 download.addEventListener('click',()=>downloadCSV(observations.map(o=>({candidate_id:row.candidate_id,name:row.name,state:row.state,district:row.district,...o})),['candidate_id','name','state','district','field','value','source_kind','source_year','observation_date','qualification','model_ready','evidence'],'house-selected-candidate-evidence.csv'));box.append(download);
 const groups=new Map();for(const observation of observations){if(!groups.has(observation.field))groups.set(observation.field,[]);groups.get(observation.field).push(observation)}
 for(const [field,items]of [...groups].sort(([a],[b])=>a.localeCompare(b))){
  const detail=el('details');detail.append(el('summary',field.replaceAll('_',' ')+' · '+items.length+' observations'));
  const wrap=el('div');wrap.className='table-wrap';const table=el('table'),head=el('thead'),header=el('tr');
  for(const name of ['Reported value','Source / date','Qualification and receipt'])header.append(el('th',name));head.append(header);table.append(head);const body=el('tbody');
  for(const item of items){const tr=el('tr'),value=el('td',pretty(item.value));value.className='evidence-value';
   const source=el('td',item.source_kind.replaceAll('_',' ')+'; source year '+pretty(item.source_year)+'; observed '+pretty(item.observation_date));
   const qualification=el('td',item.qualification);const receipt=el('details');receipt.append(el('summary','Source receipt'),el('pre',JSON.stringify(item.evidence,null,2)));qualification.append(receipt);tr.append(value,source,qualification);body.append(tr)}
  table.append(body);wrap.append(table);detail.append(wrap);box.append(detail);
 }
}
function showParticipation(box,row){
 const context=row.participation_source_context;if(!context)return;
 box.append(el('h3','Participation source context — not candidate background'));
 box.append(el('p',context.qualification));
 const state=participationStates.get(context.state_context_id);
 if(state){
  box.append(el('p',context.statewide_observations+' statewide observations; '+context.regional_observations+' separate regional rows; '+context.demographic_observations+' aggregate demographic cells. Retained snapshots have different dates. No regional counts have been assigned to this district.'));
  const detail=el('details');detail.append(el('summary','Statewide count values, definitions and source receipts'));
  for(const observation of state.statewide_observations){
   detail.append(el('p',pretty(observation.mode||observation.source_section)+': '+pretty(observation.reported_count)+' source-reported; source date '+pretty(observation.source_date)+'; count-update label '+pretty(observation.source_update_label)));
   const receipt=el('details');receipt.append(el('summary','Count definition and receipt'),el('pre',JSON.stringify(observation,null,2)));detail.append(receipt);
  }box.append(detail);
  if(state.demographic_observations.length){const groups=el('details');groups.append(el('summary','Aggregate demographic cells — not this candidate or district'),el('pre',JSON.stringify(state.demographic_observations,null,2)));box.append(groups)}
  const decision=el('details');decision.append(el('summary','State intake decision — not a common count date'),el('pre',JSON.stringify(state.source_intake_decision,null,2)));box.append(decision);
 }
 if(context.house_source_results.length){
  const results=el('details');results.append(el('summary','Supplementary House source snapshots — frozen votes unchanged'),el('p','Different snapshots and RCV rounds are not additive or vote transfers. Raw differences are not comparable electoral swings.'),el('pre',JSON.stringify(context.house_source_results,null,2)));box.append(results);
 }
 const links=el('ul');for(const url of urls([state?.statewide_observations,state?.demographic_observations,context.house_source_results])){const a=el('a',url);a.href=url;a.rel='noreferrer';const li=el('li');li.append(a);links.append(li)}box.append(links);
}
function showProfile(row){
 const box=$('profile');box.replaceChildren(el('h3',row.name+' · '+row.state+'-'+row.district));
 const fields=[
 ['Party',row.party],['Current House member',row.current_House_member?'Yes, in the pinned Clerk roster':'No qualified current-member match'],
 ['Provisional incoming classification',row.incoming_classification],['Exact date of birth',row.date_of_birth],
 ['Member/incoming education summary',row.education],['Member/incoming career summary',row.professional_history],
 ['Positive military evidence (missing is not nonservice)',row.military_service],
 ['Dated reported religion',row.religion_literal],['Religion observation date',row.religion_observation_date],
 ['Religion evidence status',row.religion_status],['Cutoff federal yea/nay votes cast',row.cast_yea_nay_votes],
 ['Background research status',row.background_research?.research_status],
 ['Research disposition',row.background_research?.disposition],
 ['Discovery correction status',row.background_discovery_repair?.discovery_status],
 ['Discovery correction disposition',row.background_discovery_repair?.disposition],
 ['Roster identity hold (not biography evidence)',row.background_discovery_repair?.roster_identity_review?.disposition],
 ['Previously missing fields filled by the correction',row.background_discovery_repair?.newly_filled_fields],
 ['Requested fields without substantive acquired observations (not negative trait labels)',Array.isArray(row.remaining_background_fields)?(row.remaining_background_fields.length?row.remaining_background_fields:'All four fields have observations; not necessarily complete or verified.'):'Not audited here: this field audit applies to election candidates.'],
 ['Comparison holds',row.comparison_holds.length?row.comparison_holds:'No hold for the selected Democratic comparison, or not the selected Democratic candidate'],
 ['Unreviewed campaign field names — not verified model inputs',row.machine_biography_fields_unreviewed]];
 for(const [label,value]of fields){const p=el('p');p.append(el('strong',label+': '),document.createTextNode(pretty(value)));box.append(p)}
 box.append(el('p','Newly attached backgrounds remain descriptive and have not been added to the trait models. Unknowns are not negative labels. A provisional winner flag is not certification.'));
 if(row.standardized_democratic_traits){const traits=el('details');traits.open=true;traits.append(el('summary','Standardized descriptive Democratic traits'),el('pre',JSON.stringify(row.standardized_democratic_traits,null,2)));box.append(traits)}
 showEvidence(box,row);
 showParticipation(box,row);
 if(row.background_research){const research=el('details');research.append(el('summary','Research receipts and access outcomes'),el('pre',JSON.stringify(row.background_research,null,2)));box.append(research)}
 if(row.background_discovery_repair?.gap_review){const review=el('details');review.append(el('summary','Reviewed-gap source receipts'),el('pre',JSON.stringify(row.background_discovery_repair.gap_review,null,2)));box.append(review)}
 if(row.background_discovery_repair?.roster_identity_review){const review=el('details');review.append(el('summary','Unresolved write-in identity: preserved roster receipt'),el('pre',JSON.stringify(row.background_discovery_repair.roster_identity_review,null,2)));box.append(review)}
 const sources=urls([row.background_evidence,row.campaign_websites,row.background_research,row.background_discovery_repair,(row.acquired_background_observations||[]).map(o=>o.evidence)]);box.append(el('h3','Source links'));
 const list=el('ul');for(const url of sources){const a=el('a',url);a.href=url;a.rel='noreferrer';const li=el('li');li.append(a);list.append(li)}box.append(list);
}
function number(value){return typeof value==='number'?value.toFixed(2):'—'}
function render(){
 const first=page*pageSize, visible=filtered.slice(first,first+pageSize);$('candidates').replaceChildren();
 for(const row of visible){const tr=el('tr');const name=el('td');const button=el('button',row.name);button.className='link';button.addEventListener('click',()=>showProfile(row));name.append(button);tr.append(name);
 for(const value of [row.state+'-'+row.district,row.party,row.votes===null?'—':Number(row.votes).toLocaleString('en-US'),number(row.presidential_gap_margin_pp),number(row.held_out_residual_margin_pp)])tr.append(el('td',value));$('candidates').append(tr)}
 $('count').textContent=filtered.length?'Showing '+(first+1)+'–'+Math.min(first+pageSize,filtered.length)+' of '+filtered.length+' profiles':'No matching profiles';
 $('previous').disabled=page===0;$('next').disabled=first+pageSize>=filtered.length;
}
const searchIndex=new WeakMap();
function searchText(row){
 if(!searchIndex.has(row))searchIndex.set(row,[row.name,row.state,row.district,row.education,row.professional_history,row.military_service,row.religion_literal,row.background_research?.research_status,row.background_research?.disposition,row.background_discovery_repair?.discovery_status,row.background_discovery_repair?.disposition,row.remaining_background_fields,...(row.acquired_background_observations||[]).map(o=>o.value)].filter(v=>v!==null&&v!==undefined).map(pretty).join(' ').toLowerCase());
 return searchIndex.get(row);
}
function filter(){
 const query=$('search').value.toLowerCase(),state=$('state').value,party=$('party').value,scope=$('scope').value;
 filtered=rows.filter(r=>(!query||searchText(r).includes(query))&&(!state||r.state===state)&&(!party||(party==='other'?!['Democratic','Republican'].includes(r.party):r.party===party))&&(!scope||(scope==='eligible'?r.comparison_eligible:scope==='current'?r.current_House_member:r.provider_winner_flag===true)));
 page=0;render();
}
for(const state of [...new Set(rows.map(r=>r.state))].sort()){const o=el('option',state);o.value=state;$('state').append(o)}
for(const id of ['search','state','party','scope'])$(id).addEventListener('input',filter);
$('dataset').addEventListener('input',()=>{rows=datasets[$('dataset').value];for(const id of ['search','state','party','scope'])$(id).value='';filter();$('profile').replaceChildren(el('p','Select a name to read the profile.'))});
$('previous').addEventListener('click',()=>{page--;render()});$('next').addEventListener('click',()=>{page++;render()});
$('download').addEventListener('click',()=>{
 const keys=['candidate_id','contest_id','name','state','district','party','votes','comparison_eligible','presidential_gap_margin_pp','held_out_residual_margin_pp','date_of_birth','education','professional_history','military_service','religion_literal','religion_status','comparison_holds','background_evidence','acquired_background_observations','standardized_democratic_traits','in_initial_research_queue','background_fields_with_observations','remaining_background_fields','background_research','background_discovery_repair','participation_source_context','background_model_ready'];
 downloadCSV(filtered,keys,'house-candidate-profiles.csv');
});
$('download-traits').addEventListener('click',()=>{
 const visible=new Set(filtered.map(r=>r.candidate_id+'\\0'+r.contest_id));
 const records=traitRows.filter(r=>visible.has(r.candidate_id+'\\0'+r.contest_id));
 downloadCSV(records,['candidate_id','contest_id','name','state','district','party','observation_count','background_fields_with_observations','remaining_background_fields','review_status','unknown_claim_count','conflicting_claim_count','standardized_claims','source_qualifications','source_urls','member_or_incoming_background','member_or_incoming_background_evidence','machine_biography_fields_unreviewed','background_research','background_discovery_repair','targeted_background_research','campaign_websites','participation_source_context','descriptive_only','model_ready'],'house-democratic-candidate-traits.csv');
});
render();
"""


def render(markdown, profiles, charts, members=None, participation=None, traits=None):
    figures = []
    for chart in charts:
        name = f"substack/{chart['id']}.png"
        figures.append(
            "<figure>"
            f'<a href="{name}" aria-label="Open full-size: {html.escape(chart["title"], quote=True)}">'
            f'<img src="{name}" alt="{html.escape(chart["alt"], quote=True)}" '
            'width="2000" height="1300" loading="lazy"></a>'
            f"<figcaption>{html.escape(chart['caption'])} "
            f'<a href="{name}">Open full-size figure</a>.</figcaption></figure>'
        )
    payload = json.dumps(profiles, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    member_payload = json.dumps(
        members or {"current": [], "incoming": []}, ensure_ascii=True, separators=(",", ":")
    ).replace("<", "\\u003c")
    participation_payload = json.dumps(
        participation or [], ensure_ascii=True, separators=(",", ":")
    ).replace("<", "\\u003c")
    trait_payload = json.dumps(traits or [], ensure_ascii=True, separators=(",", ":")).replace(
        "<", "\\u003c"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Which Democratic House candidates did better?</title>"
        f"<style>{STYLE}</style></head><body><main>"
        '<header><div class="eyebrow">Which candidate? · House research</div>'
        "<h1>Which Democrats did better?</h1>"
        '<p class="standfirst">A House-only analysis of electoral performance, voting '
        "records and candidate backgrounds. Evidence first; no universal candidate formula.</p>"
        '<nav><a href="#findings">Read the findings</a><a href="#figures">See the figures</a>'
        '<a href="#browser">Explore every candidate</a>'
        '<a href="characteristics-v3/report.html">New-source full-trait analysis (V3)</a>'
        '<a href="characteristics-v2/report.html">Frozen evidence review (V2)</a>'
        '<a href="characteristics-v1/report.html">Frozen full-trait v1</a></nav>'
        '<p class="muted">Pinned November 12–13, 2026 counts. Provisional, not certified. '
        "This local report does not republish the withdrawn website.</p></header>"
        f'<section id="findings">{article(markdown)}</section>'
        '<section id="figures"><h2>The evidence, visually</h2>'
        + "".join(figures)
        + '</section><section id="browser"><h2>Explore the candidate evidence</h2>'
        "<p>All named candidates, not only winners. Only the selected, qualified Democratic "
        "candidate receives a performance comparison. Positive values mean higher Democratic "
        "performance; these are margin points, not vote-share points or causal candidate effects. "
        "Switch to the sitting or incoming House for every seat, including vacancies and "
        "unresolved seats. Performance columns apply only to election candidates. "
        "Choose a name to inspect its background and source links.</p>"
        '<label>Dataset<select id="dataset"><option value="candidates">All election candidates</option>'
        '<option value="current">Sitting House — all 435 seats</option>'
        '<option value="incoming">Provisional incoming House — all 435 seats</option></select></label>'
        '<div class="filters"><label>Search name or background<input id="search" type="search"></label>'
        '<label>State<select id="state"><option value="">All states</option></select></label>'
        '<label>Party<select id="party"><option value="">All parties</option>'
        '<option>Democratic</option><option>Republican</option><option value="other">Other parties</option></select></label>'
        '<label>Population<select id="scope"><option value="">All named candidates</option>'
        '<option value="eligible">Qualified Democratic comparisons</option>'
        '<option value="current">Current-member matches</option>'
        '<option value="incoming">Provisional winner flags</option></select></label></div>'
        '<div class="pager"><span id="count" aria-live="polite"></span>'
        '<button id="download" type="button">Download filtered profiles (CSV)</button>'
        '<button id="download-traits" type="button">Download filtered Democratic traits (CSV)</button></div>'
        '<div class="table-wrap"><table><thead><tr><th>Name / profile</th><th>District</th>'
        "<th>Party</th><th>Source votes</th><th>Presidential gap<br>(margin pp)</th>"
        '<th>State-held-out residual<br>(margin pp)</th></tr></thead><tbody id="candidates"></tbody></table></div>'
        '<div class="pager"><button id="previous" type="button">Previous</button>'
        '<button id="next" type="button">Next</button></div>'
        '<article id="profile" aria-live="polite"><p>Select a candidate name to read the profile.</p></article>'
        "<noscript><p>The findings and figures work without JavaScript. Enable it for the "
        "local browser, or read results/house-study/candidate-profiles.csv in the complete download.</p></noscript>"
        '</section><footer><p class="muted">The complete-query archive includes code, tests, '
        "all included and held comparisons, source receipts, model samples, validation folds, "
        "member gap ledgers and exact plotted data. Frozen research is preserved. "
        "Missing evidence is never a negative trait label.</p></footer>"
        f'<script id="candidate-data" type="application/json">{payload}</script>'
        f'<script id="trait-data" type="application/json">{trait_payload}</script>'
        f'<script id="member-data" type="application/json">{member_payload}</script>'
        f'<script id="participation-data" type="application/json">{participation_payload}</script>'
        f"<script>{SCRIPT}</script></main></body></html>\n"
    )

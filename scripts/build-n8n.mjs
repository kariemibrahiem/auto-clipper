/** Build an n8n 2.x workflow. No credentials or tokens are stored in this file. */
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const nodes = [];
const connections = {};
let counter = 0;

function add(name, type, typeVersion, parameters, x, y, other = {}) {
  nodes.push({id: `auto-clip-${++counter}`, name, type, typeVersion,
    position: [x, y], parameters, ...other});
}

function connect(from, to, branch = 0) {
  connections[from] ??= {main: []};
  connections[from].main[branch] ??= [];
  connections[from].main[branch].push({node: to, type: 'main', index: 0});
}

function code(name, jsCode, x, y) {
  add(name, 'n8n-nodes-base.code', 2, {mode: 'runOnceForAllItems', jsCode}, x, y);
}

const githubHeaders = [
  {name: 'Accept', value: 'application/vnd.github+json'},
  {name: 'X-GitHub-Api-Version', value: '2022-11-28'},
];

function github(name, method, url, x, y, body, file = false) {
  const p = {method, url, authentication: 'genericCredentialType',
    genericAuthType: 'httpBearerAuth', sendHeaders: true,
    headerParameters: {parameters: githubHeaders}, options: {}};
  if (body) {
    p.sendBody = true;
    p.specifyBody = 'json';
    p.jsonBody = body;
  }
  if (file) p.options = {response: {response: {responseFormat: 'file'}}};
  add(name, 'n8n-nodes-base.httpRequest', 4.4, p, x, y,
      method === 'POST' ? {alwaysOutputData: true} : {});
}

add('Manual Trigger', 'n8n-nodes-base.manualTrigger', 1, {}, 200, 300);

code('Configure Job', `// ONLY EDIT THESE VALUES BEFORE EXECUTING.
const SOURCE_VIDEO_URL = 'PASTE_HTTPS_VIDEO_LINK_HERE';
const GITHUB_REPO = 'kariemibrahiem/auto-clipper';
const VIDEO_TITLE = 'Best Moments';
const CLIP_COUNT = 3;               // 1 to 5
const CLIP_SECONDS = 35;            // 15 to 55
const LANGUAGE = 'auto';            // 'auto', 'ar', 'en'
const NARRATION = 'on';             // 'on' or 'off'

if (!/^https:\\/\\//i.test(SOURCE_VIDEO_URL))
  throw new Error('Paste the HTTPS video URL in Configure Job first.');
if (!/^[a-zA-Z0-9_.-]+\\/[a-zA-Z0-9_.-]+$/.test(GITHUB_REPO))
  throw new Error('GITHUB_REPO must look like username/auto-clipper.');
if (CLIP_COUNT < 1 || CLIP_COUNT > 5 || CLIP_SECONDS < 15 || CLIP_SECONDS > 55)
  throw new Error('Allowed: 1–5 clips of 15–55 seconds.');
const job_id = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
return [{json:{source_url:SOURCE_VIDEO_URL, repo:GITHUB_REPO,
  job_id, run_label:'clip-' + job_id, base_title:VIDEO_TITLE,
  clip_count:CLIP_COUNT, clip_seconds:CLIP_SECONDS,
  language:LANGUAGE, narration:NARRATION, started_at:Date.now()}}];`, 410, 300);

github('Dispatch GitHub Job', 'POST',
  '={{ "https://api.github.com/repos/" + $json.repo + "/actions/workflows/clipper.yml/dispatches" }}',
  635, 300,
  `={{ JSON.stringify({ref:'main',inputs:{job_id:$json.job_id,
    source_url:$json.source_url,clip_count:String($json.clip_count),
    clip_seconds:String($json.clip_seconds),language:$json.language,
    narration:$json.narration}}) }}`);

add('Wait for GitHub', 'n8n-nodes-base.wait', 1.1, {amount: 30}, 850, 300);

github('List Clip Runs', 'GET',
  '={{ "https://api.github.com/repos/" + $("Configure Job").first().json.repo + "/actions/workflows/clipper.yml/runs?event=workflow_dispatch&per_page=100" }}',
  1050, 300);

code('Find This Job', `const cfg = $('Configure Job').first().json;
const obj = $input.first().json;
const runs = Array.isArray(obj.workflow_runs) ? obj.workflow_runs : [];
const run = runs.find(r => r.display_title === cfg.run_label);
if (Date.now() - cfg.started_at > 105 * 60 * 1000)
  throw new Error('Clipping timed out. Open GitHub Actions for details.');
if (run?.status === 'completed' && run.conclusion !== 'success')
  throw new Error('GitHub clip rendering failed: ' + run.html_url);
return [{json:{ready:run?.status === 'completed' && run.conclusion === 'success',
  github_run_id:run?.id || null, github_run_url:run?.html_url || '',
  job_id:cfg.job_id}}];`, 1250, 300);

add('Clips Ready?', 'n8n-nodes-base.if', 2.3,
  {conditions:{options:{caseSensitive:true,leftValue:'',typeValidation:'strict',version:3},
    conditions:[{id:'clip-ready-condition',leftValue:'={{ String($json.ready) }}',
      rightValue:'true',operator:{type:'string',operation:'equals'}}],combinator:'and'},
    options:{}}, 1460, 300);

github('List Run Artifacts', 'GET',
  '={{ "https://api.github.com/repos/" + $("Configure Job").first().json.repo + "/actions/runs/" + $json.github_run_id + "/artifacts?per_page=50" }}',
  1690, 250);

code('Find Clips ZIP', `const cfg = $('Configure Job').first().json;
const data = $input.first().json;
const name = 'clips-' + cfg.job_id;
const artifact = (data.artifacts || []).find(a => a.name === name && !a.expired);
if (!artifact?.archive_download_url)
  throw new Error('No clip artifact found for ' + name);
return [{json:{archive_download_url:artifact.archive_download_url}}];`, 1890, 250);

github('Download Clips ZIP', 'GET', '={{ $json.archive_download_url }}',
  2090, 250, undefined, true);

add('Unzip Clips', 'n8n-nodes-base.compression', 1.1,
    {outputPrefix:'extracted_'}, 2290, 250);

code('Prepare MP4 Items', `const cfg = $('Configure Job').first().json;
const output = [];
const items = $input.all();
for (const item of items) {
  for (const [key, binary] of Object.entries(item.binary || {})) {
    const filename = binary.fileName || '';
    if (!/\\.mp4$/i.test(filename) && binary.mimeType !== 'video/mp4') continue;
    const found = filename.match(/clip_(\\d+)\\.mp4$/i);
    if (!found) throw new Error('Unknown MP4 filename: ' + filename);
    const number = Number(found[1]);
    const base = cfg.base_title.trim() || 'Best Moments';
    const title = (base + ' | Part ' + number + ' #Shorts').slice(0, 99);
    output.push({json:{clip_number:number, title,
      description:'Highlight ' + number + ' from an authorized source. #Shorts #Highlights',
      original_source:cfg.source_url, job_id:cfg.job_id},
      binary:{data:binary}});
  }
}
output.sort((a,b) => a.json.clip_number-b.json.clip_number);
if (!output.length) throw new Error('ZIP contains no MP4 clips.');
return output;`, 2480, 250);

add('Upload Shorts to YouTube', 'n8n-nodes-base.youTube', 1,
  {resource:'video',operation:'upload',title:'={{ $json.title }}',regionCode:'EG',
    categoryId:'24',options:{description:'={{ $json.description }}',
      privacyStatus:'public',tags:'Shorts,Highlights,Clips'}},
  2700, 250, {credentials:{youTubeOAuth2Api:{
    id:'1pwrEJLIkJE2vaFF',name:'YouTube account'}}});

code('YouTube Links', `const uploaded = $input.all();
const clips = $('Prepare MP4 Items').all();
return uploaded.map((item, i) => {
  const id = item.json.uploadId || item.json.id || item.json.videoId || item.json.data?.id;
  if (!id || typeof id !== 'string')
    throw new Error('YouTube did not confirm video ID for clip ' + (i + 1));
  return {json:{clip_number:clips[i]?.json.clip_number ?? i + 1,
    title:clips[i]?.json.title || 'Short',
    url:'https://www.youtube.com/shorts/' + id,
    uploadId:id}};
});`, 2910, 250);

connect('Manual Trigger', 'Configure Job');
connect('Configure Job', 'Dispatch GitHub Job');
connect('Dispatch GitHub Job', 'Wait for GitHub');
connect('Wait for GitHub', 'List Clip Runs');
connect('List Clip Runs', 'Find This Job');
connect('Find This Job', 'Clips Ready?');
connect('Clips Ready?', 'List Run Artifacts', 0);
connect('Clips Ready?', 'Wait for GitHub', 1);
connect('List Run Artifacts', 'Find Clips ZIP');
connect('Find Clips ZIP', 'Download Clips ZIP');
connect('Download Clips ZIP', 'Unzip Clips');
connect('Unzip Clips', 'Prepare MP4 Items');
connect('Prepare MP4 Items', 'Upload Shorts to YouTube');
connect('Upload Shorts to YouTube', 'YouTube Links');

const workflow = {
  name:'Auto Clipping | GitHub FFmpeg + Narration + YouTube Shorts',
  nodes, connections,
  settings:{executionOrder:'v1'},
  active:false,
  pinData:{},
  meta:{templateCredsSetupCompleted:false},
};
const output = path.join(root, 'n8n', 'Auto_Clipping_YouTube_n8n.json');
fs.writeFileSync(output, JSON.stringify(workflow, null, 2) + '\n');
console.log('Created', output, nodes.length, 'nodes');

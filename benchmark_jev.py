"""Read-only repeated decision latency pilot. Sends no game inputs."""
import argparse,json,pathlib,statistics,time
from jev_bridge import JevClient
from observe_game import Observer
root=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--pid',type=int,required=True)
args=parser.parse_args()
obs=Observer(args.pid)
try:raw=obs.snapshot()
finally:obs.close()
if not any(m['name']=='start' and m['labels'] for m in raw['menus']):
 raise RuntimeError('Run this read-only benchmark at the main menu')
state={'game':'Fallout: New Vegas','menu':'start',
       'visible_items':list(dict.fromkeys(v['text'] for m in raw['menus'] if m['name']=='start' for v in m['labels'])),
       'recording_active':False,'objective':'Start a fresh recorded campaign after capture is verified'}
questions={'action':{'type':'choice','instructions':'Choose whether to begin now or wait for active verified recording.',
    'criteria':{'wait':'Wait at the main menu while recording is not active','start':'Begin the new campaign because recording is active'}}}
client=JevClient();results=[]
try:
 for i in range(6):
  r=client.request(state,questions);results.append(r)
  print(json.dumps({'sample':i+1,'choice':r['answers']['action']['choice'],'latency_ms':round(r['latency_seconds']*1000,1)}),flush=True)
finally:client.close()
summary={'purpose':'Repeated menu-prerequisite decisions; no inputs executed',
 'cold_ms':round(results[0]['latency_seconds']*1000,1),
 'warm_median_ms':round(statistics.median(x['latency_seconds'] for x in results[1:])*1000,1),
 'warm_max_ms':round(max(x['latency_seconds'] for x in results[1:])*1000,1),
 'samples':len(results),'all_wait':all(x['answers']['action']['choice']=='wait' for x in results),
 'estimated_usd':sum(x['estimated_usd'] for x in results),'results':results}
(root/'jev-latency-pilot.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='results'}))

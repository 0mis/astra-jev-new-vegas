"""Bounded Jev decision client. Credentials are read only from the environment."""
import json, os, time, http.client, pathlib, datetime,math,msvcrt,uuid
ROOT = pathlib.Path(__file__).resolve().parent
LEDGER = ROOT / "jev-usage.jsonl"
PRICE = 0.042 / 1_000_000
CAP = 1.0

def ledger_total(rows):
    """Keep uncertain requests reserved; charge confirmed usage once per request."""
    legacy, pending = 0.0, {}
    for row in rows:
        ident = row.get('request_id')
        if not ident:
            legacy += row.get('reserved_usd', 0)
        elif 'reserved_usd' in row:
            if ident in pending: raise RuntimeError('Duplicate budget reservation')
            pending[ident] = row['reserved_usd']
        elif 'settled_usd' in row:
            if ident not in pending: raise RuntimeError('Settlement without reservation')
            cost = row['settled_usd']
            if not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                raise RuntimeError('Invalid usage cost')
            pending[ident] = cost
    return legacy + sum(pending.values())

def append_ledger(row):
    with LEDGER.open('a', encoding='utf-8') as output:
        output.write(json.dumps(row)+'\n'); output.flush(); os.fsync(output.fileno())

class JevClient:
    """One persistent TLS connection and one owner of the conservative cost ledger."""
    def __init__(self,timeout=5):
        self.key=os.environ.get('TYPESAFE_API_KEY')
        if not self.key:raise RuntimeError('No authorized TypeSafe credential in this process')
        self.lock=(ROOT/'jev-client.lock').open('a+b');self.lock.seek(0)
        if not self.lock.read(1):self.lock.write(b'0');self.lock.flush()
        self.lock.seek(0);msvcrt.locking(self.lock.fileno(),msvcrt.LK_NBLCK,1)
        previous=[json.loads(s) for s in LEDGER.read_text().splitlines()] if LEDGER.exists() else []
        self.spent=ledger_total(previous)
        self.connection=http.client.HTTPSConnection('api.typesafe.ai',timeout=timeout)
    def close(self):
        self.connection.close()
        if not self.lock.closed:
            self.lock.seek(0);msvcrt.locking(self.lock.fileno(),msvcrt.LK_UNLCK,1);self.lock.close()
        self.key=None
    def request(self,state,questions):
        body=json.dumps({'model':'jev-1.13.0','state':state,'questions':questions},separators=(',',':')).encode()
        reserved=(len(body)*2+4096)*PRICE
        if self.spent+reserved>CAP:raise RuntimeError('Conservative $1 test budget reached')
        request_id=str(uuid.uuid4())
        row={'request_id':request_id,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'reserved_usd':reserved,'request_bytes':len(body)}
        append_ledger(row)
        self.spent+=reserved
        started=time.perf_counter()
        try:
            self.connection.request('POST','/v1/systemone',body=body,
                headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
            response=self.connection.getresponse();raw=response.read()
            if response.status!=200:raise RuntimeError(f'TypeSafe HTTP {response.status}; no automatic retry')
            data=json.loads(raw)
        except BaseException:
            self.connection.close()
            raise
        elapsed=time.perf_counter()-started
        if set(data['answers'])!=set(questions):raise RuntimeError('Unexpected answer keys')
        for name,question in questions.items():
            answer=data['answers'][name]
            if question['type']=='choice':
                if answer['choice'] not in question['criteria']:raise RuntimeError('Response outside permitted choices')
                confidence=answer['confidence']
                if not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not 0<=confidence<=1:
                    raise RuntimeError('Invalid confidence')
        result={'answers':data['answers'],'latency_seconds':round(elapsed,4),'usage':data.get('usage'),
                'model':data['model'],'estimated_usd':data.get('usage',{}).get('input_tokens',0)*PRICE}
        settlement={'request_id':request_id,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'usage':result['usage'],'latency_seconds':result['latency_seconds']}
        tokens=(result['usage'] or {}).get('input_tokens')
        if isinstance(tokens,int) and not isinstance(tokens,bool) and tokens>0:
            settlement['settled_usd']=tokens*PRICE
        append_ledger(settlement)
        if 'settled_usd' in settlement:
            self.spent+=settlement['settled_usd']-reserved
        result['request_id']=request_id
        return result

_client=None
def decide(state, options, instructions):
    global _client
    if _client is None:_client=JevClient()
    result=_client.request(state,{'action':{'type':'choice','instructions':instructions,'criteria':options}})
    answer=result.pop('answers')['action']
    return dict(result,choice=answer['choice'],confidence=answer['confidence'],probabilities=answer.get('probabilities'))

def commentary(speaker, text, kind="public_gameplay_update"):
    event={"at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "speaker":speaker,"kind":kind,"text":text}
    with (ROOT/"commentary.jsonl").open("a",encoding="utf-8") as f:
        f.write(json.dumps(event,ensure_ascii=False)+"\n")
    return event

if __name__=="__main__":
    result=decide(
      {"game":"Fallout: New Vegas","phase":"setup","recording_verified":False,
       "objective":"Complete the main story while preserving all gameplay footage",
       "fact":"The game has not started. Recording must be verified before gameplay."},
      {"wait_for_recording":"Stay in setup until real video and audio capture are verified",
       "start_new_game":"Start playing the campaign now",
       "claim_completion":"Report that the campaign has already been beaten"},
      "Choose the appropriate next step from the observed facts. Never claim unobserved progress.")
    (ROOT/"jev-smoke-test.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result))

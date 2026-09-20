"""Bounded Jev decision client. Credentials are read only from the environment."""
import json, os, time, urllib.request, pathlib, datetime
ROOT = pathlib.Path(__file__).resolve().parent
LEDGER = ROOT / "jev-usage.jsonl"
PRICE = 0.042 / 1_000_000
CAP = 1.0

def decide(state, options, instructions):
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise RuntimeError("No authorized TypeSafe credential in this process")
    # This single-owner client deliberately has no automatic retries after uncertain calls.
    previous = [json.loads(s) for s in LEDGER.read_text().splitlines()] if LEDGER.exists() else []
    spent = sum(x.get("reserved_usd", 0) for x in previous)
    body = json.dumps({"model":"jev-1.13.0", "state":state, "questions":{
        "action":{"type":"choice","instructions":instructions,"criteria":options}
    }}).encode()
    reserved = (len(body) * 2 + 4096) * PRICE
    if spent + reserved > CAP:
        raise RuntimeError("Conservative $1 test budget reached")
    row={"at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "reserved_usd":reserved,"request_bytes":len(body)}
    with LEDGER.open("a",encoding="utf-8") as f: f.write(json.dumps(row)+"\n")
    req=urllib.request.Request("https://api.typesafe.ai/v1/systemone",data=body,
        headers={"Authorization":"Bearer "+os.environ["TYPESAFE_API_KEY"],"Content-Type":"application/json"})
    started=time.perf_counter()
    with urllib.request.urlopen(req,timeout=30) as r: data=json.load(r)
    elapsed=time.perf_counter()-started
    answer=data["answers"]["action"]
    if answer["choice"] not in options: raise RuntimeError("Response outside permitted choices")
    return {"choice":answer["choice"],"confidence":answer["confidence"],
            "latency_seconds":round(elapsed,4),"usage":data.get("usage"),
            "model":data["model"],"estimated_usd":data.get("usage",{}).get("input_tokens",0)*PRICE}

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

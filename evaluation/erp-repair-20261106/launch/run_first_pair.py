from datetime import datetime,timezone
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from run_validation import run,api_client,base,AUTH
from grade_validation import grade
def main():
    lookup={r['request_id']:r for r in json.loads((ROOT/'REQUESTS.json').read_text())['requests']}
    rows=json.loads((ROOT/'SCHEDULE.json').read_text())['sessions'][:2]
    base.write_json(ROOT/'launch/BUDGET_BEFORE_RETEST.json',api_client.budget_state())
    for row in rows:
     directory=ROOT/'sessions'/row['session']
     result=run(lookup[row['request_id']],row)
     if result['status'] not in ('submitted','failed'):
      base.write_json(ROOT/'FORMAL_ADMISSION_STOP.json',{'session':row['session'],'status':result['status'],'error':result.get('error'),'reason':'First controlled pair infrastructure/budget failure; preserve outputs and stop new admission'})
      raise SystemExit('First controlled pair is incomplete')
     grade(lookup[row['request_id']],result,directory)
    base.write_json(ROOT/'launch/FIRST_PAIR_COMPLETE.json',{'sessions':[r['session'] for r in rows],'completed_at_utc':datetime.now(timezone.utc).isoformat(),'shared_budget':api_client.budget_state(),'scientific_outcome_not_a_launch_gate':True})
    print('FIRST_PAIR_COMPLETE',flush=True)


if __name__ == '__main__':
    main()

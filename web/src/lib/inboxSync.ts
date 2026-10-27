/** Resumable Gmail verification. Only the existing authenticated client sends requests. */
export interface InboxCoverage {days:number; gmail:number; in_ace:number; missing:number; checked_at:string; complete:boolean}
export interface SyncStep {state:string; counts:Record<string,number>; remaining:number; partial:boolean; coverage:InboxCoverage}
type RecheckStep = {state?:string; checked:number; remaining:number; counts:Record<string,number>};
type Post = <T>(path:string, body:Record<string,number>)=>Promise<T>;

export function coverageText(coverage:InboxCoverage|null|undefined):string {
  if(!coverage)return "Email coverage has not been verified since the server started. Check Gmail to verify it.";
  const total=coverage.gmail.toLocaleString("en-US");
  const missing=coverage.missing.toLocaleString("en-US");
  if(!coverage.complete)return `Gmail listing is incomplete for the last ${coverage.days} days. ${total} emails checked so far; ${missing} are not in ACE yet.`;
  return `Gmail has ${total} emails from the last ${coverage.days} days. ${coverage.missing?`${missing} are not in ACE yet.`:"All are in ACE."}`;
}

export async function verifyInbox({days,stale,post,progress,active=()=>true}:{days:number;stale:number;post:Post;progress:(note:string,coverage?:InboxCoverage)=>void;active?:()=>boolean}) {
  const counts:Record<string,number>={};
  let rechecked=0,recorded=0;
  const check=()=>{if(!active())throw new Error("Inbox verification stopped. Saved progress will resume on the next check.");};
  // Each server batch saves independently; a failed request leaves progress
  // intact and propagates its real error. Never present a failure as success.
  for(let round=0;;round++){
    check();
    if(round>=1000)throw new Error("More email remains. Check Gmail again to continue saved progress.");
    const step=await post<SyncStep>("/api/inbox/sync",{days});
    check();
    if(step.state!=="ready")throw new Error(step.state==="busy"?"Another Inbox check is running. Try again shortly.":"Gmail sync is paused or disconnected. Saved progress is kept.");
    if(!step.coverage)throw new Error("Gmail did not return verified coverage. Check again.");
    for(const [key,value] of Object.entries(step.counts))counts[key]=(counts[key]??0)+value;
    progress(`${step.coverage.in_ace.toLocaleString("en-US")} of ${step.coverage.gmail.toLocaleString("en-US")} emails in ACE for ${days} days`,step.coverage);
    if(!step.remaining){
      if(step.partial||!step.coverage.complete)throw new Error("Gmail listing could not finish. Coverage is incomplete; try again later.");
      break;
    }
  }
  if(stale>0)for(let round=0;;round++){
    check();
    if(round>=1000)throw new Error("More older email remains to re-read. Check again to continue.");
    progress(`Reading older email again with the newest rules: ${rechecked} of ${stale}`);
    const step=await post<RecheckStep>("/api/inbox/recheck",{limit:25});
    check();
    if(step.state==="busy")throw new Error("Another Inbox check is running. Try again shortly.");
    rechecked+=step.checked;recorded+=step.counts.automatic??0;
    if(!step.remaining)break;
    if(!step.checked)throw new Error("Older email could not finish rechecking. Check again to continue.");
  }
  return {counts,rechecked,recorded};
}

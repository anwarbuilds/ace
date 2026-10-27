/** Resumable Gmail verification. Only the existing authenticated client sends requests. */
export interface InboxCoverage {days:number; scope?:"all"|"job_mail"; includes_spam_trash?:boolean; phase?:string; gmail:number; in_ace:number; missing:number; checked_at:string; complete:boolean}
export interface SyncStep {state:string; counts:Record<string,number>; remaining:number; partial:boolean; more?:boolean; coverage:InboxCoverage}
type RecheckStep = {scope_pending?:boolean;state?:string; checked:number; remaining:number; counts:Record<string,number>};
type Post = <T>(path:string, body:Record<string,number>)=>Promise<T>;

export function coverageText(coverage:InboxCoverage|null|undefined):string {
  if(!coverage)return "Email coverage has not been verified since the server started. Check Gmail to verify it.";
  const total=coverage.gmail.toLocaleString("en-US");
  const missing=coverage.missing.toLocaleString("en-US");
  const jobScope=coverage.scope==="job_mail";
  if(coverage.days===0){
    const scope=jobScope?"matching the job-mail search across all dates, including archived mail; Spam and Trash excluded":"across the previously checked retained history";
    if(!coverage.complete)return `Full Gmail verification is incomplete. ${total} emails found so far ${scope}; ${missing} known emails remain to import. Listing and change checks may find more.`;
    return `Gmail has ${total} emails ${scope}. ${coverage.missing?`${missing} are not in ACE yet.`:"All are in ACE for this checked snapshot."} ${jobScope?"Search terms may miss some job mail. ":""}Permanently deleted mail is unavailable.`;
  }
  if(!coverage.complete)return `Gmail listing is incomplete for the last ${coverage.days} days. ${total} emails checked so far; ${missing} are not in ACE yet.`;
  return `Gmail has ${total} ${jobScope?"job-mail search candidates":"emails"} from the last ${coverage.days} days. ${coverage.missing?`${missing} are not in ACE yet.`:"All are in ACE."} This window does not verify your full mailbox history.`;
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
    if(step.coverage.scope!=="job_mail")throw new Error("The server has not verified job-mail scope. Check again after the Inbox update is available.");
    if(step.coverage.days!==days)throw new Error("Gmail coverage is for a different history selection. Check again.");
    for(const [key,value] of Object.entries(step.counts))counts[key]=(counts[key]??0)+value;
    progress(days===0?coverageText(step.coverage):`${step.coverage.in_ace.toLocaleString("en-US")} of ${step.coverage.gmail.toLocaleString("en-US")} emails in ACE for ${days} days`,step.coverage);
    if(step.more)continue;
    if(!step.remaining){
      if(step.partial||!step.coverage.complete)throw new Error("Gmail listing could not finish. Coverage is incomplete; try again later.");
      break;
    }
  }
  if(days===0||stale>0)for(let round=0;;round++){
    check();
    if(round>=1000)throw new Error("More older email remains to re-read. Check again to continue.");
    progress(`Reading older email again with the newest rules: ${rechecked} of ${stale}`);
    const step=await post<RecheckStep>("/api/inbox/recheck",{limit:25});
    check();
    if(step.state&&step.state!=="ready")throw new Error(step.state==="busy"?"Another Inbox check is running. Try again shortly.":"Gmail recheck stopped because the connection was paused or changed. Saved progress is kept.");
    if(step.scope_pending)throw new Error("Job-mail scope needs verification before older email can be rechecked. Saved evidence is kept; check Gmail again.");
    rechecked+=step.checked;recorded+=step.counts.automatic??0;
    if(!step.remaining)break;
    if(!step.checked)throw new Error("Older email could not finish rechecking. Check again to continue.");
  }
  return {counts,rechecked,recorded};
}

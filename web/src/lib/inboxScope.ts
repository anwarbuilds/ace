/** The server's receipt-date boundary for visible Inbox evidence. */
export interface InboxEvidenceScope {
  start:string;
  timezone:string;
  start_at:string;
  application_cohort_unchanged:boolean;
}

export function inboxHistoryLabel(scope:InboxEvidenceScope):string {
  const day=new Date(`${scope.start}T12:00:00Z`);
  return `Since ${day.toLocaleDateString("en-US",{timeZone:"UTC",month:"long",day:"numeric",year:"numeric"})}`;
}

export function outsideInboxHistory(receivedAt:string,scope:InboxEvidenceScope|undefined):boolean {
  return Boolean(scope&&Date.parse(receivedAt)<Date.parse(scope.start_at));
}

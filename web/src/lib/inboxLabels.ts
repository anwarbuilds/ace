/** What ACE read the email as. */
export const KIND: Record<string,string> = {rejection:"Rejection",possible_rejection:"Possible rejection",interview:"Interview",online_assessment:"Assessment",offer:"Offer",recruiter_reply:"Recruiter reply",application_confirmation:"Acknowledgement",unclear:"Application correspondence",unknown:"No outcome found"};
/** What happened to it. */
export const STATE: Record<string,string> = {review:"Needs you",exact_preview:"Needs you",deferred:"Decide later",automatic:"Recorded by ACE",manual:"Recorded by you",receipt:"Acknowledgement",update:"Saved correspondence",unrelated:"Not about applications",ignored:"Nothing recorded"};

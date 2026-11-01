/** Compare authoritative projections without storing a second metrics ledger.
 * Only the read timestamp is excluded; every returned data field participates. */
export async function analyticsFingerprint(value: object): Promise<string> {
  const canonical=(input:unknown):unknown=>{
    if(Array.isArray(input))return input.map(canonical);
    if(input&&typeof input==="object")return Object.fromEntries(Object.entries(input).filter(([key])=>key!=="as_of").sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>[key,canonical(item)]));
    return input;
  };
  const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(JSON.stringify(canonical(value))));
  return [...new Uint8Array(digest)].map(byte=>byte.toString(16).padStart(2,"0")).join("");
}

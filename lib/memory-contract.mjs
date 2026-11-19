// Shared policy for the thin V1/V2 adapters. No backend, permission or storage
// operations here. Keep this module outside auto-discovered plugin directories.
const keyword = /\b(remember|memorize|save\s+this|don'?t\s+forget|note\s+this|keep\s+in\s+mind)\b/i;

export const MEMORY_HINT = `[MEMORY HINT]
The user explicitly asked to remember something.

If the information is durable and useful across sessions, call the appropriate Engram memory tool now.
- Use project memory for repo-specific conventions, architecture, commands, or gotchas.
- Use user/global memory for stable user preferences that apply beyond this repo.
- Do not persist raw secrets or anything wrapped in <private>...</private>.
- Save concise, reusable knowledge instead of raw conversation text.`;

export function needsMemoryHint(text) {
  return typeof text === 'string' && keyword.test(text.trim());
}

export function injectSummarySession(tool, sessionID, args) {
  if (tool !== 'engram_mem_session_summary' || typeof sessionID !== 'string' || !sessionID.trim()) return;
  if (!args || typeof args !== 'object' || Array.isArray(args)) return;
  if (typeof args.session_id === 'string' && args.session_id.trim()) return;
  args.session_id = sessionID;
}

import { MEMORY_HINT, needsMemoryHint, injectSummarySession } from '../../../lib/memory-contract.mjs';

export function addMemoryHints(event, originals) {
  // LLM messages use role/content; persisted SessionMessage uses type/text.
  // Match their IDs against actual user records, not attachment text, tool
  // results, synthetic messages or an in-memory map lost after restart.
  const requested = new Set(originals.filter(message => message.type === 'user' && needsMemoryHint(message.text)).map(message => message.id));
  event.messages = event.messages.map(message => {
    if (message.role !== 'user' || !message.id || !requested.has(message.id)) return message;
    if (message.content.some(part => part.type === 'text' && part.text === MEMORY_HINT)) return message;
    return { ...message, content: [...message.content, { type: 'text', text: MEMORY_HINT }] };
  });
}

export async function register(ctx) {
  await ctx.tool.hook('execute.before', event => injectSummarySession(event.tool, event.sessionID, event.input));
  const hint = async event => {
    if (!event.messages.some(message => message.role === 'user')) return;
    const originals = await ctx.session.context({ sessionID: event.sessionID });
    addMemoryHints(event, originals);
  };
  // Reconstruct the synthetic hint in the outgoing context without rewriting
  // durable user text or starting another turn. Include compaction replay.
  for (const kind of ['context', 'compaction', 'generate']) await ctx.session.hook(kind, hint);
}

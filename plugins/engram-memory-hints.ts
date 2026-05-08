import type { Part } from "@opencode-ai/sdk"
import type { Plugin } from "@opencode-ai/plugin"

const MEMORY_KEYWORD_PATTERN = /\b(remember|memorize|save\s+this|don'?t\s+forget|note\s+this|keep\s+in\s+mind)\b/i

const MEMORY_HINT = `[MEMORY HINT]
The user explicitly asked to remember something.

If the information is durable and useful across sessions, call the appropriate Engram memory tool now.
- Use project memory for repo-specific conventions, architecture, commands, or gotchas.
- Use user/global memory for stable user preferences that apply beyond this repo.
- Do not persist raw secrets or anything wrapped in <private>...</private>.
- Save concise, reusable knowledge instead of raw conversation text.`

const EngramMemoryHintsPlugin: Plugin = async () => ({
  "chat.message": async (input, output) => {
    const text = output.parts
      .filter((part): part is Part & { type: "text"; text: string } => part.type === "text")
      .filter((part) => !part.synthetic)
      .map((part) => part.text)
      .join("\n")
      .trim()

    if (!text || !MEMORY_KEYWORD_PATTERN.test(text)) return

    output.parts.push({
      id: `prt_memory_hint_${Date.now()}`,
      sessionID: input.sessionID,
      messageID: output.message.id,
      type: "text",
      text: MEMORY_HINT,
      synthetic: true,
    })
  },
})

export default EngramMemoryHintsPlugin

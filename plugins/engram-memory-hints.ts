import type { Part } from "@opencode-ai/sdk"
import type { Plugin } from "@opencode-ai/plugin"
import { MEMORY_HINT, needsMemoryHint } from "../lib/memory-contract.mjs"

const EngramMemoryHintsPlugin: Plugin = async () => ({
  "chat.message": async (input, output) => {
    const text = output.parts
      .filter((part): part is Part & { type: "text"; text: string } => part.type === "text")
      .filter((part) => !part.synthetic)
      .map((part) => part.text)
      .join("\n")
      .trim()

    if (!needsMemoryHint(text)) return

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

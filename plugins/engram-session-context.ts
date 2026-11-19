import type { Plugin } from "@opencode-ai/plugin"
import { injectSummarySession } from "../lib/memory-contract.mjs"

const EngramSessionContextPlugin: Plugin = async () => ({
  "tool.execute.before": async (input, output) => {
    injectSummarySession(input.tool, input.sessionID, output.args)
  },
})

export default EngramSessionContextPlugin

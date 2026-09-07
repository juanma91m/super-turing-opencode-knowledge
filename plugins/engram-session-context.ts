import type { Plugin } from "@opencode-ai/plugin"

type BeforeToolInput = {
  tool: string
  sessionID: string
  callID: string
}

type BeforeToolOutput = {
  args: Record<string, unknown>
}

function injectEngramSummarySession(
  input: BeforeToolInput,
  output: BeforeToolOutput,
): void {
  if (input.tool !== "engram_mem_session_summary") return
  if (!input.sessionID.trim()) return

  const explicitSessionID = output.args.session_id
  if (typeof explicitSessionID === "string" && explicitSessionID.trim()) return

  output.args.session_id = input.sessionID
}

const EngramSessionContextPlugin: Plugin = async () => ({
  "tool.execute.before": async (input, output) => {
    injectEngramSummarySession(input, output)
  },
})

export default EngramSessionContextPlugin

import assert from "node:assert/strict"
import test from "node:test"

import EngramSessionContextPlugin from "../plugins/engram-session-context.ts"
import * as EngramMemoryHintsModule from "../plugins/engram-memory-hints.ts"
import * as EngramSessionContextModule from "../plugins/engram-session-context.ts"

test("every auto-discovered plugin export is a valid plugin factory", async () => {
  const modules = {
    "engram-memory-hints": EngramMemoryHintsModule,
    "engram-session-context": EngramSessionContextModule,
  }

  for (const [moduleName, pluginModule] of Object.entries(modules)) {
    for (const [exportName, factory] of Object.entries(pluginModule)) {
      assert.equal(typeof factory, "function", `${moduleName}.${exportName} must be a function`)
      const hooks = await factory({} as never)
      assert.ok(
        hooks && typeof hooks === "object",
        `${moduleName}.${exportName} must return a hooks object`,
      )
    }
  }
})

test("injects the OpenCode session ID into Engram session summaries", async () => {
  const hooks = await EngramSessionContextPlugin({} as never)
  const output = { args: { content: "summary" } }

  await hooks["tool.execute.before"](
    { tool: "engram_mem_session_summary", sessionID: "ses-opencode-123", callID: "call-1" },
    output,
  )

  assert.equal(output.args.session_id, "ses-opencode-123")
})

test("preserves an explicit summary session ID", async () => {
  const hooks = await EngramSessionContextPlugin({} as never)
  const output = { args: { content: "summary", session_id: "explicit-session" } }

  await hooks["tool.execute.before"](
    { tool: "engram_mem_session_summary", sessionID: "ses-opencode-123", callID: "call-1" },
    output,
  )

  assert.equal(output.args.session_id, "explicit-session")
})

test("does not modify unrelated tool calls", async () => {
  const hooks = await EngramSessionContextPlugin({} as never)
  const output = { args: { content: "memory" } }

  await hooks["tool.execute.before"](
    { tool: "engram_mem_save", sessionID: "ses-opencode-123", callID: "call-1" },
    output,
  )

  assert.deepEqual(output.args, { content: "memory" })
})

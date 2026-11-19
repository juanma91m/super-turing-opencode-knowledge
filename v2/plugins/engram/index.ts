import { Plugin } from "@opencode/plugin"
import { register } from "./hooks.mjs"

export default Plugin.define({ id: "opencode-knowledge.engram", setup: register })

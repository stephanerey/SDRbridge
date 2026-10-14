#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const runner = path.join(__dirname, "sr_ui_verify.mjs");
const args = process.argv.slice(2);

console.error("deprecated: scripts/codex/playwright_auth_smoke.mjs now delegates to sr_ui_verify.mjs");
const proc = spawnSync(process.execPath, [runner, ...args], { stdio: "inherit" });
process.exit(proc.status ?? 3);

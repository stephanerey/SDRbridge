#!/usr/bin/env node
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const EXIT = { pass: 0, fail: 1, blocked: 2, config_error: 3 };

const DEFAULT_CONFIG = {
  enabled: true,
  runner: { command: "node scripts/codex/sr_ui_verify.mjs" },
  base_url: { env: "PLAYWRIGHT_BASE_URL", default: "http://localhost:3000" },
  routes: [],
  viewports: [
    { name: "desktop-xl", width: 1440, height: 900 },
    { name: "desktop", width: 1280, height: 800 },
    { name: "tablet", width: 768, height: 1024 },
    { name: "mobile", width: 390, height: 844 },
  ],
  auth: {
    required: false,
    mode: "none",
    storage_state: { path: ".playwright/.auth/user.json" },
    setup_command: null,
    login_detection: {
      url_patterns: ["/login", "/signin", "/auth", "/oauth/", "/oidc/", "/if/flow/"],
    },
  },
  checks: {
    screenshots: true,
    console_errors: true,
    console_error_ignore_patterns: [],
    page_errors: true,
    request_failed: "warn",
    request_failed_ignore_patterns: [],
    horizontal_overflow: true,
    horizontal_overflow_tolerance_px: 2,
    unexpected_login_redirect: true,
    wait_until: "domcontentloaded",
    wait_after_ms: 300,
  },
  evidence: {
    directory: "output/playwright",
    report_file: "output/playwright/ui-verification-report.json",
  },
};

function parseArgs(argv) {
  const args = { routes: [] };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (arg === "--route" && next) {
      args.routes.push(next);
      i += 1;
    } else if (arg === "--routes" && next) {
      args.routes.push(...next.split(",").map((item) => item.trim()).filter(Boolean));
      i += 1;
    } else if (arg === "--config" && next) {
      args.config = next;
      i += 1;
    } else if (arg === "--base-url" && next) {
      args.baseUrl = next;
      i += 1;
    } else if (arg === "--report-file" && next) {
      args.reportFile = next;
      i += 1;
    } else if (arg === "--output-dir" && next) {
      args.outputDir = next;
      i += 1;
    } else if (arg === "--auth-mode" && next) {
      args.authMode = next;
      i += 1;
    } else if (arg === "--storage-state" && next) {
      args.storageState = next;
      i += 1;
    } else if (arg === "--help") {
      args.help = true;
    }
  }
  return args;
}

function usage() {
  return `Usage: node scripts/codex/sr_ui_verify.mjs [--config PROJECT_PROFILE.yaml|config.json] [--route /path] [--routes /a,/b] [--base-url URL]

Exit codes:
  0 pass
  1 fail
  2 blocked
  3 config_error`;
}

function deepMerge(base, override) {
  const out = Array.isArray(base) ? [...base] : { ...base };
  for (const [key, value] of Object.entries(override || {})) {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      base &&
      typeof base[key] === "object" &&
      !Array.isArray(base[key])
    ) {
      out[key] = deepMerge(base[key], value);
    } else if (value !== undefined) {
      out[key] = value;
    }
  }
  return out;
}

function stripQuotes(value) {
  const trimmed = String(value).trim();
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function scalar(value) {
  const clean = stripQuotes(String(value).split(" #")[0].trim());
  if (clean === "null" || clean === "~") return null;
  if (clean === "true") return true;
  if (clean === "false") return false;
  if (/^-?\d+$/.test(clean)) return Number.parseInt(clean, 10);
  return clean;
}

function topLevelSection(text, name) {
  const lines = text.split(/\r?\n/);
  const start = lines.findIndex((line) => line.trim() === `${name}:`);
  if (start < 0) return "";
  const out = [];
  for (let i = start + 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (/^\S[^:]*:\s*/.test(line)) break;
    out.push(line);
  }
  return out.join("\n");
}

function nestedBlock(text, key) {
  const lines = text.split(/\r?\n/);
  const index = lines.findIndex((line) => new RegExp(`^\\s*${key}:\\s*$`).test(line));
  if (index < 0) return "";
  const indent = lines[index].match(/^\s*/)[0].length;
  const out = [];
  for (let i = index + 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.trim()) {
      out.push(line);
      continue;
    }
    const currentIndent = line.match(/^\s*/)[0].length;
    if (currentIndent <= indent) break;
    out.push(line.slice(indent + 2));
  }
  return out.join("\n");
}

function yamlValue(text, key) {
  const match = text.match(new RegExp(`^\\s*${key}:\\s*(.+?)\\s*$`, "m"));
  return match ? scalar(match[1]) : undefined;
}

function yamlScalarList(text, key) {
  const block = nestedBlock(text, key);
  if (!block) return undefined;
  const values = [];
  for (const line of block.split(/\r?\n/)) {
    const match = line.match(/^\s*-\s+(.+?)\s*$/);
    if (match) values.push(scalar(match[1]));
  }
  return values;
}

function yamlObjectList(text, key) {
  const block = nestedBlock(text, key);
  if (!block) return undefined;
  const items = [];
  let current = null;
  for (const line of block.split(/\r?\n/)) {
    const first = line.match(/^\s*-\s+([a-zA-Z0-9_-]+):\s*(.+?)\s*$/);
    if (first) {
      current = { [first[1]]: scalar(first[2]) };
      items.push(current);
      continue;
    }
    const next = line.match(/^\s+([a-zA-Z0-9_-]+):\s*(.+?)\s*$/);
    if (next && current) current[next[1]] = scalar(next[2]);
  }
  return items;
}

function parseUiValidationYaml(text) {
  const ui = topLevelSection(text, "ui_validation");
  if (!ui) return {};
  const auth = nestedBlock(ui, "auth");
  const storage = nestedBlock(auth, "storage_state");
  const loginDetection = nestedBlock(auth, "login_detection");
  const baseUrl = nestedBlock(ui, "base_url");
  const runner = nestedBlock(ui, "runner");
  const checks = nestedBlock(ui, "checks");
  const evidence = nestedBlock(ui, "evidence");
  const parsed = {
    enabled: yamlValue(ui, "enabled"),
    runner: { command: yamlValue(runner, "command") },
    base_url: { env: yamlValue(baseUrl, "env"), default: yamlValue(baseUrl, "default") },
    routes: yamlScalarList(ui, "routes"),
    viewports: yamlObjectList(ui, "viewports"),
    auth: {
      required: yamlValue(auth, "required"),
      mode: yamlValue(auth, "mode"),
      storage_state: { path: yamlValue(storage, "path") },
      setup_command: yamlValue(auth, "setup_command"),
      login_detection: { url_patterns: yamlScalarList(loginDetection, "url_patterns") },
    },
    checks: {
      screenshots: yamlValue(checks, "screenshots"),
      console_errors: yamlValue(checks, "console_errors"),
      console_error_ignore_patterns: yamlScalarList(checks, "console_error_ignore_patterns"),
      page_errors: yamlValue(checks, "page_errors"),
      request_failed: yamlValue(checks, "request_failed"),
      request_failed_ignore_patterns: yamlScalarList(checks, "request_failed_ignore_patterns"),
      horizontal_overflow: yamlValue(checks, "horizontal_overflow"),
      horizontal_overflow_tolerance_px: yamlValue(checks, "horizontal_overflow_tolerance_px"),
      unexpected_login_redirect: yamlValue(checks, "unexpected_login_redirect"),
      wait_until: yamlValue(checks, "wait_until"),
      wait_after_ms: yamlValue(checks, "wait_after_ms"),
    },
    evidence: {
      directory: yamlValue(evidence, "directory"),
      report_file: yamlValue(evidence, "report_file"),
    },
  };
  return removeUndefined(parsed);
}

function removeUndefined(value) {
  if (Array.isArray(value)) return value.map(removeUndefined).filter((item) => item !== undefined);
  if (!value || typeof value !== "object") return value;
  const out = {};
  for (const [key, child] of Object.entries(value)) {
    const cleaned = removeUndefined(child);
    if (cleaned !== undefined && !(typeof cleaned === "object" && !Array.isArray(cleaned) && Object.keys(cleaned).length === 0)) {
      out[key] = cleaned;
    }
  }
  return out;
}

function loadConfig(configPath) {
  if (!configPath) {
    const candidates = ["docs/codex/PROJECT_PROFILE.yaml", "core/PROJECT_PROFILE.template.yaml"];
    configPath = candidates.find((candidate) => fs.existsSync(candidate));
  }
  if (!configPath || !fs.existsSync(configPath)) return {};
  const text = fs.readFileSync(configPath, "utf8");
  if (configPath.endsWith(".json")) {
    const data = JSON.parse(text);
    return data.ui_validation || data;
  }
  return parseUiValidationYaml(text);
}

function normalizeRoute(route) {
  if (!route) return "/";
  return route.startsWith("/") ? route : `/${route}`;
}

function routeSlug(route) {
  const clean = normalizeRoute(route).replace(/^\/+/, "").replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-|-$/g, "");
  return clean || "root";
}

function absoluteUrl(baseUrl, route) {
  const base = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  return `${base}${normalizeRoute(route)}`;
}

function matchesAny(value, patterns) {
  return (patterns || []).some((pattern) => {
    if (!pattern) return false;
    if (pattern.startsWith("regex:")) return new RegExp(pattern.slice(6)).test(value);
    return value.includes(pattern);
  });
}

function filtered(value, patterns) {
  return matchesAny(value, patterns || []);
}

function writeReport(reportFile, report) {
  fs.mkdirSync(path.dirname(reportFile), { recursive: true });
  fs.writeFileSync(reportFile, `${JSON.stringify(report, null, 2)}\n`, "utf8");
}

function worstStatus(previous, current) {
  const rank = { pass: 0, fail: 1, blocked: 2 };
  if (!previous) return current;
  return rank[current] > rank[previous] ? current : previous;
}

function setupAuth(command) {
  if (!command) return { ran: false, ok: false };
  const proc = spawnSync(command, { shell: true, stdio: "pipe", encoding: "utf8" });
  return { ran: true, ok: proc.status === 0, status: proc.status };
}

function readinessBlocked(message, config, baseUrl, routes, reportFile) {
  const report = {
    status: "blocked",
    base_url: baseUrl,
    generated_at: new Date().toISOString(),
    auth: {
      required: config.auth.required,
      mode: config.auth.mode,
      state_file: config.auth.storage_state?.path || null,
      login_redirect_detected: false,
    },
    ui_test_readiness_gate: {
      required: true,
      application: { reachable: null, base_url: baseUrl },
      authentication: {
        required: config.auth.required,
        mode: config.auth.mode,
        state_available: config.auth.storage_state?.path ? fs.existsSync(config.auth.storage_state.path) : null,
        state_valid: false,
        login_redirect_detected: false,
      },
      routes: routes.map((route) => ({ route, reachable: null })),
      blocked_reason: message,
      decision: "blocked",
    },
    ui_visual_evidence_gate: { required: true, decision: "blocked", screenshots: [], technical_checks: {} },
    routes: [],
  };
  writeReport(reportFile, report);
  console.log(JSON.stringify({ status: report.status, report_file: reportFile, reason: message }, null, 2));
  return EXIT.blocked;
}

async function run() {
  const args = parseArgs(process.argv);
  if (args.help) {
    console.log(usage());
    return EXIT.pass;
  }

  let fileConfig = {};
  try {
    fileConfig = loadConfig(args.config);
  } catch (error) {
    console.error(`sr_ui_verify config_error: ${error.message}`);
    return EXIT.config_error;
  }

  const config = deepMerge(DEFAULT_CONFIG, fileConfig);
  if (args.authMode) config.auth.mode = args.authMode;
  if (args.storageState) config.auth.storage_state.path = args.storageState;
  if (args.reportFile) config.evidence.report_file = args.reportFile;
  if (args.outputDir) config.evidence.directory = args.outputDir;

  const baseUrl = args.baseUrl || process.env[config.base_url.env || "PLAYWRIGHT_BASE_URL"] || config.base_url.default;
  const routes = (args.routes.length ? args.routes : config.routes.length ? config.routes : ["/"]).map(normalizeRoute);
  const reportFile = config.evidence.report_file;
  const outputDir = config.evidence.directory;
  const loginPatterns = config.auth.login_detection?.url_patterns || DEFAULT_CONFIG.auth.login_detection.url_patterns;

  if (config.enabled === false) {
    const report = {
      status: "not_applicable",
      base_url: baseUrl,
      generated_at: new Date().toISOString(),
      ui_test_readiness_gate: { required: false, decision: "not_applicable" },
      ui_visual_evidence_gate: { required: false, decision: "not_applicable" },
      routes: [],
    };
    writeReport(reportFile, report);
    console.log(JSON.stringify({ status: "not_applicable", report_file: reportFile }, null, 2));
    return EXIT.pass;
  }

  const authRequired = config.auth.required === true;
  const authMode = config.auth.mode || "none";
  const storageStatePath = config.auth.storage_state?.path;
  if (authRequired && authMode === "manual") {
    return readinessBlocked("auth mode manual requires human session preparation", config, baseUrl, routes, reportFile);
  }
  if (authRequired && authMode === "storage_state" && storageStatePath && !fs.existsSync(storageStatePath)) {
    const setup = setupAuth(config.auth.setup_command);
    if (!setup.ok || !fs.existsSync(storageStatePath)) {
      return readinessBlocked("storageState missing and setup_command did not create a usable session", config, baseUrl, routes, reportFile);
    }
  }
  if (authRequired && authMode === "setup_command") {
    const setup = setupAuth(config.auth.setup_command);
    if (!setup.ok) return readinessBlocked("setup_command failed", config, baseUrl, routes, reportFile);
  }

  const report = {
    status: "pass",
    base_url: baseUrl,
    generated_at: new Date().toISOString(),
    auth: {
      required: authRequired,
      mode: authMode,
      state_file: authMode === "storage_state" ? storageStatePath : null,
      login_redirect_detected: false,
    },
    ui_test_readiness_gate: {
      required: true,
      application: { reachable: false, base_url: baseUrl },
      authentication: {
        required: authRequired,
        mode: authMode,
        state_available: authMode === "storage_state" && storageStatePath ? fs.existsSync(storageStatePath) : null,
        state_valid: authMode === "storage_state" ? null : true,
        login_redirect_detected: false,
      },
      routes: [],
      decision: "pass",
    },
    ui_visual_evidence_gate: {
      required: true,
      routes,
      viewports: {},
      technical_checks: {
        console_errors: 0,
        page_errors: 0,
        request_failed: 0,
        horizontal_overflow: false,
        unexpected_login_redirect: false,
      },
      design_check: { required: false, status: "not_applicable" },
      screenshots: [],
      decision: "pass",
    },
    routes: [],
  };

  let browser;
  try {
    browser = await chromium.launch({ headless: true });
  } catch (error) {
    console.error(`sr_ui_verify config_error: ${error.message}`);
    return EXIT.config_error;
  }

  try {
    for (const route of routes) {
      const routeResult = { route, viewports: [] };
      report.routes.push(routeResult);
      for (const viewport of config.viewports) {
        const consoleErrors = [];
        const pageErrors = [];
        const requestFailed = [];
        const contextOptions = { viewport: { width: viewport.width, height: viewport.height } };
        if (authMode === "storage_state" && storageStatePath && fs.existsSync(storageStatePath)) {
          contextOptions.storageState = storageStatePath;
        }
        const context = await browser.newContext(contextOptions);
        const page = await context.newPage();
        page.on("console", (msg) => {
          if (msg.type() === "error" && !filtered(msg.text(), config.checks.console_error_ignore_patterns)) {
            consoleErrors.push(msg.text());
          }
        });
        page.on("pageerror", (error) => pageErrors.push(error.message));
        page.on("requestfailed", (request) => {
          const failure = `${request.url()} ${request.failure()?.errorText || ""}`.trim();
          if (!filtered(failure, config.checks.request_failed_ignore_patterns)) requestFailed.push(failure);
        });

        const target = absoluteUrl(baseUrl, route);
        let response = null;
        let gotoError = null;
        try {
          response = await page.goto(target, {
            waitUntil: config.checks.wait_until || "domcontentloaded",
            timeout: 30000,
          });
          if (config.checks.wait_after_ms) await page.waitForTimeout(config.checks.wait_after_ms);
        } catch (error) {
          gotoError = error.message;
        }

        const finalUrl = page.url();
        const loginRedirectDetected = matchesAny(finalUrl, loginPatterns);
        const statusCode = response ? response.status() : null;
        const reachable = !gotoError && statusCode !== null && statusCode < 500;
        const overflow = config.checks.horizontal_overflow
          ? await page.evaluate((tolerance) => {
              const doc = document.documentElement;
              return doc.scrollWidth > doc.clientWidth + tolerance;
            }, config.checks.horizontal_overflow_tolerance_px || 0).catch(() => false)
          : false;

        const screenshotRel = path.join(outputDir, routeSlug(route), `${viewport.name}.png`);
        if (config.checks.screenshots) {
          fs.mkdirSync(path.dirname(screenshotRel), { recursive: true });
          await page.screenshot({ path: screenshotRel, fullPage: true }).catch(() => null);
          report.ui_visual_evidence_gate.screenshots.push(screenshotRel);
        }

        let status = "pass";
        const failures = [];
        if (gotoError) {
          status = "fail";
          failures.push(`navigation failed: ${gotoError}`);
        }
        if (statusCode !== null && statusCode >= 400) {
          status = "fail";
          failures.push(`http status ${statusCode}`);
        }
        if (loginRedirectDetected && config.checks.unexpected_login_redirect) {
          status = authRequired ? "blocked" : "fail";
          failures.push(`login redirect detected: ${finalUrl}`);
        }
        if (config.checks.page_errors && pageErrors.length) {
          status = "fail";
          failures.push("pageerror detected");
        }
        if (config.checks.console_errors && consoleErrors.length) {
          status = "fail";
          failures.push("console.error detected");
        }
        if (config.checks.request_failed === "fail" && requestFailed.length) {
          status = "fail";
          failures.push("requestfailed detected");
        }
        if (overflow) {
          status = "fail";
          failures.push("horizontal overflow detected");
        }

        routeResult.viewports.push({
          name: viewport.name,
          width: viewport.width,
          height: viewport.height,
          status,
          requested_url: target,
          final_url: finalUrl,
          http_status: statusCode,
          screenshot: config.checks.screenshots ? screenshotRel : null,
          console_errors: consoleErrors,
          page_errors: pageErrors,
          request_failed: requestFailed,
          horizontal_overflow: overflow,
          login_redirect_detected: loginRedirectDetected,
          failures,
        });

        report.ui_test_readiness_gate.application.reachable ||= reachable;
        const readinessRoute = report.ui_test_readiness_gate.routes.find((item) => item.route === route);
        if (readinessRoute) {
          readinessRoute.reachable ||= reachable;
          readinessRoute.login_redirect_detected ||= loginRedirectDetected;
        } else {
          report.ui_test_readiness_gate.routes.push({ route, reachable, login_redirect_detected: loginRedirectDetected });
        }
        report.auth.login_redirect_detected ||= loginRedirectDetected;
        report.ui_test_readiness_gate.authentication.login_redirect_detected ||= loginRedirectDetected;
        if (authMode === "storage_state" && authRequired && !loginRedirectDetected && reachable) {
          report.ui_test_readiness_gate.authentication.state_valid = true;
        }

        report.ui_visual_evidence_gate.viewports[viewport.name] = worstStatus(
          report.ui_visual_evidence_gate.viewports[viewport.name],
          status
        );
        report.ui_visual_evidence_gate.technical_checks.console_errors += consoleErrors.length;
        report.ui_visual_evidence_gate.technical_checks.page_errors += pageErrors.length;
        report.ui_visual_evidence_gate.technical_checks.request_failed += requestFailed.length;
        report.ui_visual_evidence_gate.technical_checks.horizontal_overflow ||= overflow;
        report.ui_visual_evidence_gate.technical_checks.unexpected_login_redirect ||= loginRedirectDetected;

        await context.close();
      }
    }
  } finally {
    await browser.close().catch(() => null);
  }

  const allViewportResults = report.routes.flatMap((route) => route.viewports);
  const anyBlocked = allViewportResults.some((item) => item.status === "blocked");
  const anyFail = allViewportResults.some((item) => item.status === "fail");
  const anyLogin = allViewportResults.some((item) => item.login_redirect_detected);
  const anyUnreachable = report.ui_test_readiness_gate.routes.some((item) => !item.reachable);

  if (anyLogin) {
    report.ui_test_readiness_gate.decision = authRequired ? "blocked" : "fail";
  } else if (anyUnreachable) {
    report.ui_test_readiness_gate.decision = "fail";
  }
  if (anyBlocked) {
    report.status = "blocked";
    report.ui_visual_evidence_gate.decision = "blocked";
  } else if (anyFail || report.ui_test_readiness_gate.decision === "fail") {
    report.status = "fail";
    report.ui_visual_evidence_gate.decision = "repair";
  }
  if (report.ui_test_readiness_gate.decision === "blocked") {
    report.status = "blocked";
    report.ui_visual_evidence_gate.decision = "blocked";
  }

  writeReport(reportFile, report);
  console.log(JSON.stringify({ status: report.status, report_file: reportFile }, null, 2));
  if (report.status === "pass") return EXIT.pass;
  if (report.status === "blocked") return EXIT.blocked;
  return EXIT.fail;
}

run().then((code) => process.exit(code)).catch((error) => {
  console.error(`sr_ui_verify config_error: ${error.message}`);
  process.exit(EXIT.config_error);
});

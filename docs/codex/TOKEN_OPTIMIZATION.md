# Token and cache policy — SR 4.1

## Input

- permanent SR context target: at most 1,500 tokens;
- ordinary SR overhead target: at most 3,000 uncached tokens;
- complex-pass SR overhead target: at most 8,000 uncached tokens;
- zero to two method skills normally, three maximum for a complex pass.

Load exact ranges and triggered procedures. Keep raw logs and large artifacts outside context; inject a bounded summary and stable path. Retry a corrected tool call at most once.

## Output

Lead with the result. Ordinary closure should fit in about 400 words. Report only used evidence, relevant limits and remaining acceptance.

## Cache

Keep permanent instructions, tool definitions and their order stable. Put task-specific and volatile content later. Add deferred tools append-only; prefer allowlists over rebuilding the catalog.

Track separately: context occupancy, uncached input, cached input or writes, output, reasoning when available, tool-result volume and retries. Cached tokens still occupy context and must not be discounted in the context-pressure gate.

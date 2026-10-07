import { appendFileSync } from "node:fs";

// Resource override only. Preserve prompts, messages, tools and sampling settings.
export default function (pi: any) {
  pi.on("before_provider_request", (event: any) => {
    const raw = process.env.AGENTIC_MAX_OUTPUT_TOKENS;
    if (!raw) return;
    const limit = Number(raw);
    if (!Number.isSafeInteger(limit) || limit <= 0) {
      throw new Error("AGENTIC_MAX_OUTPUT_TOKENS must be a positive integer");
    }
    const payload = event.payload;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error("expected OpenAI completion request object");
    }
    const field = "max_tokens" in payload ? "max_tokens" : "max_completion_tokens";
    const result = { ...payload, [field]: limit };
    appendFileSync("/logs/agent/output-budget.jsonl", JSON.stringify({
      model: payload.model, field, previous: payload[field] ?? null, requested: limit,
    }) + "\n", { mode: 0o600 });
    return result;
  });
}

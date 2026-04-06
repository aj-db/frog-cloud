/** Lightweight human hints for common cron patterns (not a full cron parser). */
export function cronHint(expression: string): string {
  const parts = expression.trim().split(/\s+/);
  if (parts.length < 5) return expression;
  const [minute, hour, dom, month, dow] = parts;

  if (minute === "0" && hour === "0" && dom === "*" && month === "*" && dow === "*") {
    return "Every day at midnight";
  }
  if (minute === "0" && hour === "12" && dom === "*" && month === "*" && dow === "*") {
    return "Every day at noon";
  }
  if (minute === "0" && dom === "*" && month === "*" && dow === "*" && hour !== "*") {
    return `Daily at ${hour}:00`;
  }
  if (minute.startsWith("*/") && hour === "*" && dom === "*" && month === "*" && dow === "*") {
    const n = minute.slice(2);
    return `Every ${n} minutes`;
  }
  return expression;
}

// Shared helpers for every feature's job-progress UI (anonymous stories,
// film summary, ...): the step-state machine and the backend error_code ->
// i18n key mapping. Pulled out of the per-feature lib modules (which used
// to each carry their own near-identical copy) to remove that duplication.

/**
 * State of a single step given the job's overall status, which stage index
 * is currently reported (-1 when none has been reported yet), and this
 * step's own index. Kept as its own function (flattened to early returns)
 * to keep cognitive complexity low -- a nested closure with the same
 * branching counts every branch twice (once for its own nesting, once for
 * being inside the outer function).
 */
export function resolveJobStepState(status, stageIndex, index) {
    if (status === "complete") return "done";
    if (index < stageIndex) return "done";

    const isCurrentStep = index === stageIndex || (stageIndex === -1 && index === 0);
    if (!isCurrentStep) return "pending";
    return status === "error" ? "error" : "active";
}

/**
 * Map a backend error_code (e.g. "NOT_A_STORY") to its i18n key under the
 * given namespace (e.g. "anonymousStories.errorNotAStory"). Falls back to
 * `fallback` when no code is given -- the caller's `t()` call handles a
 * missing translation.
 */
export function errorMessageForCodeWithNamespace(t, namespace, code, fallback) {
    if (!code) return fallback;
    const camel = String(code).toLowerCase().replace(/_([a-z0-9])/g, (_match, c) => c.toUpperCase());
    const key = `${namespace}.error${camel.charAt(0).toUpperCase()}${camel.slice(1)}`;
    return t(key, fallback);
}

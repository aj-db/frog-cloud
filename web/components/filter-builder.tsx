"use client";

import { useCallback, useMemo } from "react";
import {
  createFilterRule,
  defaultOperator,
  FILTER_FIELDS,
  getFieldDef,
  getOperatorsForField,
  type FilterLogic,
  type FilterRule,
} from "@/lib/filter-fields";

interface FilterBuilderProps {
  rules: FilterRule[];
  logic: FilterLogic;
  onRulesChange: (rules: FilterRule[]) => void;
  onLogicChange: (logic: FilterLogic) => void;
  issueTypes?: string[];
}

export function FilterBuilder({
  rules,
  logic,
  onRulesChange,
  onLogicChange,
  issueTypes = [],
}: FilterBuilderProps) {
  const addRule = useCallback(() => {
    onRulesChange([...rules, createFilterRule()]);
  }, [rules, onRulesChange]);

  const removeRule = useCallback(
    (id: string) => {
      onRulesChange(rules.filter((r) => r.id !== id));
    },
    [rules, onRulesChange],
  );

  const updateRule = useCallback(
    (id: string, patch: Partial<FilterRule>) => {
      onRulesChange(
        rules.map((r) => (r.id === id ? { ...r, ...patch } : r)),
      );
    },
    [rules, onRulesChange],
  );

  const clearAll = useCallback(() => {
    onRulesChange([]);
  }, [onRulesChange]);

  const groups = useMemo(() => {
    const g = new Map<string, typeof FILTER_FIELDS>();
    for (const f of FILTER_FIELDS) {
      const list = g.get(f.group) ?? [];
      list.push(f);
      g.set(f.group, list);
    }
    return g;
  }, []);

  return (
    <div className="ds-card space-y-2 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <LogicToggle value={logic} onChange={onLogicChange} />

        <button
          type="button"
          className="ds-btn ds-btn--secondary gap-1 text-[11px]"
          onClick={addRule}
        >
          <PlusIcon />
          Add filter
        </button>

        {rules.length > 0 && (
          <button
            type="button"
            className="ds-btn ds-btn--ghost text-[11px]"
            onClick={clearAll}
          >
            Clear all
          </button>
        )}

        <span className="ml-auto text-[11px] text-[var(--muted)]">
          {rules.length === 0
            ? "No filters applied"
            : `${rules.length} filter${rules.length === 1 ? "" : "s"}`}
        </span>
      </div>

      {rules.length > 0 && (
        <div className="space-y-1.5">
          {rules.map((rule, idx) => (
            <RuleRow
              key={rule.id}
              rule={rule}
              groups={groups}
              issueTypes={issueTypes}
              onUpdate={(patch) => updateRule(rule.id, patch)}
              onRemove={() => removeRule(rule.id)}
              showLogicLabel={idx > 0}
              logic={logic}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function LogicToggle({
  value,
  onChange,
}: {
  value: FilterLogic;
  onChange: (v: FilterLogic) => void;
}) {
  return (
    <div className="inline-flex overflow-hidden rounded-md border border-[var(--border)] text-[11px] font-semibold">
      <button
        type="button"
        className={`px-2.5 py-1 transition-colors ${
          value === "and"
            ? "bg-[var(--charcoal)] text-white"
            : "bg-[var(--card)] text-[var(--muted)] hover:bg-[var(--light-grey)]"
        }`}
        onClick={() => onChange("and")}
      >
        AND
      </button>
      <button
        type="button"
        className={`border-l border-[var(--border)] px-2.5 py-1 transition-colors ${
          value === "or"
            ? "bg-[var(--charcoal)] text-white"
            : "bg-[var(--card)] text-[var(--muted)] hover:bg-[var(--light-grey)]"
        }`}
        onClick={() => onChange("or")}
      >
        OR
      </button>
    </div>
  );
}

function RuleRow({
  rule,
  groups,
  issueTypes,
  onUpdate,
  onRemove,
  showLogicLabel,
  logic,
}: {
  rule: FilterRule;
  groups: Map<string, typeof FILTER_FIELDS>;
  issueTypes: string[];
  onUpdate: (patch: Partial<FilterRule>) => void;
  onRemove: () => void;
  showLogicLabel: boolean;
  logic: FilterLogic;
}) {
  const operators = useMemo(() => getOperatorsForField(rule.field), [rule.field]);
  const currentOp = useMemo(
    () => operators.find((o) => o.value === rule.op),
    [operators, rule.op],
  );
  const needsValue = currentOp?.needsValue ?? true;
  const isIssueTypeField = rule.field === "issue_type";

  return (
    <div className="flex items-center gap-1.5">
      {showLogicLabel ? (
        <span className="w-8 shrink-0 text-center text-[10px] font-bold uppercase text-[var(--muted)]">
          {logic}
        </span>
      ) : (
        <span className="w-8 shrink-0" />
      )}

      {/* Field selector */}
      <select
        value={rule.field}
        onChange={(e) => {
          const newField = e.target.value;
          onUpdate({
            field: newField,
            op: defaultOperator(newField),
            value: "",
          });
        }}
        className="ds-select min-w-[140px] max-w-[180px] py-1.5 pl-2 pr-6 text-[12px]"
      >
        {Array.from(groups.entries()).map(([group, fields]) => (
          <optgroup key={group} label={group}>
            {fields.map((f) => (
              <option key={f.key} value={f.key}>
                {f.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>

      {/* Operator selector */}
      <select
        value={rule.op}
        onChange={(e) => onUpdate({ op: e.target.value })}
        className="ds-select min-w-[120px] max-w-[170px] py-1.5 pl-2 pr-6 text-[12px]"
      >
        {operators.map((op) => (
          <option key={op.value} value={op.value}>
            {op.label}
          </option>
        ))}
      </select>

      {/* Value input */}
      {needsValue ? (
        isIssueTypeField && issueTypes.length > 0 ? (
          <select
            value={rule.value}
            onChange={(e) => onUpdate({ value: e.target.value })}
            className="ds-select min-w-[140px] flex-1 py-1.5 pl-2 pr-6 text-[12px]"
          >
            <option value="">Select issue type...</option>
            {issueTypes.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        ) : (
          <input
            type={getFieldDef(rule.field)?.type === "number" ? "number" : "text"}
            value={rule.value}
            onChange={(e) => onUpdate({ value: e.target.value })}
            placeholder="Value..."
            className="ds-input min-w-[100px] flex-1 py-1.5 pl-2 pr-2 text-[12px]"
          />
        )
      ) : (
        <span className="flex-1" />
      )}

      {/* Remove button */}
      <button
        type="button"
        onClick={onRemove}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-[var(--muted)] transition-colors hover:bg-[var(--light-grey)] hover:text-[var(--red)]"
        title="Remove filter"
      >
        <XIcon />
      </button>
    </div>
  );
}

function PlusIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M6 2v8M2 6h8" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3 3l6 6M9 3l-6 6" />
    </svg>
  );
}

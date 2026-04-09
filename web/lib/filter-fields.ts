export type FieldType = "string" | "number" | "boolean";

export interface FilterFieldDef {
  key: string;
  label: string;
  type: FieldType;
  group: string;
}

export interface FilterRule {
  id: string;
  field: string;
  op: string;
  value: string;
}

export type FilterLogic = "and" | "or";

export const FILTER_FIELDS: FilterFieldDef[] = [
  // General
  { key: "address", label: "URL / Address", type: "string", group: "General" },
  { key: "status_code", label: "Status Code", type: "number", group: "General" },
  { key: "content_type", label: "Content Type", type: "string", group: "General" },
  { key: "redirect_url", label: "Redirect URL", type: "string", group: "General" },
  { key: "http_version", label: "HTTP Version", type: "string", group: "General" },

  // SEO
  { key: "title", label: "Title", type: "string", group: "SEO" },
  { key: "meta_description", label: "Meta Description", type: "string", group: "SEO" },
  { key: "h1", label: "H1", type: "string", group: "SEO" },
  { key: "indexability", label: "Indexability", type: "string", group: "SEO" },
  { key: "canonical", label: "Canonical", type: "string", group: "SEO" },
  { key: "canonical_link_element", label: "Canonical Link Element", type: "string", group: "SEO" },
  { key: "meta_robots", label: "Meta Robots", type: "string", group: "SEO" },
  { key: "x_robots_tag", label: "X-Robots-Tag", type: "string", group: "SEO" },
  { key: "pagination_status", label: "Pagination", type: "string", group: "SEO" },
  { key: "in_sitemap", label: "In Sitemap", type: "boolean", group: "SEO" },

  // Technical
  { key: "word_count", label: "Word Count", type: "number", group: "Technical" },
  { key: "crawl_depth", label: "Crawl Depth", type: "number", group: "Technical" },
  { key: "response_time", label: "Response Time", type: "number", group: "Technical" },
  { key: "size_bytes", label: "Size (bytes)", type: "number", group: "Technical" },

  // Links
  { key: "inlinks", label: "Inlinks", type: "number", group: "Links" },
  { key: "outlinks", label: "Outlinks", type: "number", group: "Links" },
  { key: "link_score", label: "Link Score", type: "number", group: "Links" },

  // Pseudo-fields
  { key: "has_issues", label: "Has Issues", type: "boolean", group: "Issues" },
  { key: "issue_type", label: "Issue Type", type: "string", group: "Issues" },
];

const FIELD_MAP = new Map(FILTER_FIELDS.map((f) => [f.key, f]));

export interface OperatorDef {
  value: string;
  label: string;
  needsValue: boolean;
}

export const STRING_OPERATORS: OperatorDef[] = [
  { value: "contains", label: "contains", needsValue: true },
  { value: "not_contains", label: "does not contain", needsValue: true },
  { value: "equals", label: "equals", needsValue: true },
  { value: "not_equals", label: "does not equal", needsValue: true },
  { value: "starts_with", label: "starts with", needsValue: true },
  { value: "ends_with", label: "ends with", needsValue: true },
  { value: "is_empty", label: "is empty", needsValue: false },
  { value: "is_not_empty", label: "is not empty", needsValue: false },
  { value: "regex", label: "matches regex", needsValue: true },
];

export const NUMBER_OPERATORS: OperatorDef[] = [
  { value: "eq", label: "equals", needsValue: true },
  { value: "neq", label: "does not equal", needsValue: true },
  { value: "gt", label: "greater than", needsValue: true },
  { value: "gte", label: "greater than or equal", needsValue: true },
  { value: "lt", label: "less than", needsValue: true },
  { value: "lte", label: "less than or equal", needsValue: true },
  { value: "is_empty", label: "is empty", needsValue: false },
  { value: "is_not_empty", label: "is not empty", needsValue: false },
];

export const BOOLEAN_OPERATORS: OperatorDef[] = [
  { value: "is_true", label: "is true", needsValue: false },
  { value: "is_false", label: "is false", needsValue: false },
  { value: "is_empty", label: "is empty", needsValue: false },
];

export function getOperatorsForField(fieldKey: string): OperatorDef[] {
  const def = FIELD_MAP.get(fieldKey);
  if (!def) return STRING_OPERATORS;
  switch (def.type) {
    case "string":
      return STRING_OPERATORS;
    case "number":
      return NUMBER_OPERATORS;
    case "boolean":
      return BOOLEAN_OPERATORS;
  }
}

export function getFieldDef(fieldKey: string): FilterFieldDef | undefined {
  return FIELD_MAP.get(fieldKey);
}

export function defaultOperator(fieldKey: string): string {
  const ops = getOperatorsForField(fieldKey);
  return ops[0]?.value ?? "contains";
}

let _counter = 0;
export function createFilterRule(field = "address"): FilterRule {
  _counter += 1;
  return {
    id: `rule-${Date.now()}-${_counter}`,
    field,
    op: defaultOperator(field),
    value: "",
  };
}

export const LOCATION_FILTERS = ["all", "local_or_regional", "local", "regional", "distant", "unknown"];

export function opportunityLocationScope(item) {
  return item?.score?.location?.scope ?? "unknown";
}

export function matchesLocationFilter(item, filter) {
  const scope = opportunityLocationScope(item);
  if (filter === "all") return true;
  if (filter === "local_or_regional") return scope === "local" || scope === "regional";
  return scope === filter;
}

export function countLocationScopes(items) {
  const counts = { local: 0, regional: 0, distant: 0, unknown: 0 };
  for (const item of items) {
    const scope = opportunityLocationScope(item);
    if (scope in counts) counts[scope] += 1;
    else counts.unknown += 1;
  }
  return counts;
}

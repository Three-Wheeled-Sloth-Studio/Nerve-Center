import type { ReviewOpportunity } from "./types";

export type LocationFilter = "all" | "local_or_regional" | "local" | "regional" | "distant" | "unknown";
export type LocationCounts = { local: number; regional: number; distant: number; unknown: number };

export const LOCATION_FILTERS: LocationFilter[];
export function opportunityLocationScope(item: ReviewOpportunity): "local" | "regional" | "distant" | "unknown";
export function matchesLocationFilter(item: ReviewOpportunity, filter: LocationFilter): boolean;
export function countLocationScopes(items: ReviewOpportunity[]): LocationCounts;

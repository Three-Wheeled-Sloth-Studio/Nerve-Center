export function Metric({ label, value }: { label: string; value: number | undefined }) { return <div><span>{label}</span><strong>{score(value)}</strong></div>; }
export function score(value: number | undefined) { return value === undefined ? "--" : Math.round(value).toString(); }
export function lines(value: string) { return Array.from(new Set(value.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean))); }
export function messageOf(reason: unknown) { return reason instanceof Error ? reason.message : String(reason); }
export function remaining(deadline: string | null) { if (!deadline) return "No deadline"; const seconds = Math.max(0, Math.round((new Date(deadline).getTime() - Date.now()) / 1000)); return seconds < 60 ? `${seconds}s remaining` : `${Math.floor(seconds / 60)}m remaining`; }
export function formatDuration(seconds: number) { if (seconds < 60) return `${Math.round(seconds)}s`; const minutes = Math.round(seconds / 60); return minutes < 60 ? `${minutes}m` : `${Math.round(minutes / 60)}h`; }
export function titleCase(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }

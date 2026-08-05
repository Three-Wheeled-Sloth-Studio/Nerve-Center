export function parseMultivalueText(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/\r\n|\n|\r/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

export function formatMultivalueText(values: string[]): string {
  return values.join("\n");
}

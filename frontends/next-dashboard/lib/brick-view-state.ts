export type BrickViewMetadata = {
  id: string;
  name: string;
  description?: string;
};

export function normalizeBrickViews(views: BrickViewMetadata[]): BrickViewMetadata[] {
  const seen = new Set<string>();
  return views.filter((view) => {
    if (!view.id || seen.has(view.id)) return false;
    seen.add(view.id);
    return true;
  });
}

export function resolveBrickViewId(
  views: BrickViewMetadata[],
  selectedId: string | undefined,
  fallbackIndex = 0,
): string | undefined {
  if (selectedId && views.some((view) => view.id === selectedId)) return selectedId;
  if (views.length === 0) return undefined;
  const index = Math.min(Math.max(fallbackIndex, 0), views.length - 1);
  return views[index]?.id ?? views[0].id;
}

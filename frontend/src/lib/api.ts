export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

/** Resolve image_url from a defect record to a browser-loadable URL. */
export function resolveImageUrl(imageUrl: string): string {
  if (!imageUrl) return '';
  if (imageUrl.startsWith('http://') || imageUrl.startsWith('https://')) return imageUrl;
  if (imageUrl.startsWith('/demo-data') || imageUrl.startsWith('demo-data')) return imageUrl;
  // /static/defects/... or bare path → prepend API_BASE
  return API_BASE + (imageUrl.startsWith('/') ? imageUrl : `/${imageUrl}`);
}

/** Fetch latest enrichment for a defect. Returns null if 404 or network error. */
export async function getDefectEnrichment(
  defectId: number,
): Promise<import("@/types/defect").DefectEnrichmentRead | null> {
  try {
    const resp = await fetch(`${API_BASE}/api/defects/${defectId}/enrichment`);
    if (resp.status === 404) return null;
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

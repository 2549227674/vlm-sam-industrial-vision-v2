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

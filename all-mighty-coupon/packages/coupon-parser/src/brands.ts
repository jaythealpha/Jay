import type { FieldCandidate } from '@amc/shared-types';

/**
 * Brand matching against a curated dictionary (server-side table post-M0).
 * Aliases cover OCR variants; matching is case/space-insensitive.
 */

export interface BrandEntry {
  name: string;
  aliases: string[];
}

export const DEFAULT_BRANDS: BrandEntry[] = [
  { name: '스타벅스', aliases: ['starbucks', 'starbucks coffee', '스타벅스커피'] },
  { name: '투썸플레이스', aliases: ['a twosome place', 'twosome'] },
  { name: '배스킨라빈스', aliases: ['baskin robbins', 'baskinrobbins', '베스킨라빈스'] },
  { name: 'GS25', aliases: ['gs 25', 'gs편의점'] },
  { name: 'CU', aliases: ['씨유'] },
  { name: '이마트', aliases: ['emart', 'e-mart'] },
  { name: '올리브영', aliases: ['olive young', 'oliveyoung'] },
  { name: '교촌치킨', aliases: ['kyochon', '교촌'] },
  { name: 'BHC', aliases: ['비에이치씨'] },
  { name: '파리바게뜨', aliases: ['paris baguette', '파리바게트'] },
];

function normalize(s: string): string {
  return s.toLowerCase().replace(/\s+/g, '');
}

export function matchBrand(
  text: string,
  brands: readonly BrandEntry[] = DEFAULT_BRANDS,
): FieldCandidate<string> | null {
  const haystack = normalize(text);
  for (const brand of brands) {
    if (haystack.includes(normalize(brand.name))) {
      return { value: brand.name, confidence: 0.95 };
    }
    if (brand.aliases.some((alias) => haystack.includes(normalize(alias)))) {
      return { value: brand.name, confidence: 0.85 };
    }
  }
  return null;
}

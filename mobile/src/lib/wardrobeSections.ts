import { COLORS } from '@/constants/wardrobe-taxonomy';
import {
  itemDisplayName,
  type WardrobeApiItem,
  type WardrobeCategorySummary,
} from '@/lib/wardrobeApi';

export type WardrobeGroupMode = 'SYSTEM_CATEGORY' | 'CUSTOM_CATEGORY';
export type WardrobeItemSort = 'ADDED_DESC' | 'COLOR_NAME_ASC';

export type WardrobeSectionFilters = {
  selectedCategories: string[];
  query: string;
  systemCategoryOrder: string[];
  customCategoryOrder: WardrobeCategorySummary[];
};

export type WardrobeSection = {
  id: string;
  title: string;
  items: WardrobeApiItem[];
};

export const UNCATEGORIZED_SECTION_ID = 'virtual:uncategorized';

const colorRank = new Map<string, number>(COLORS.map((color, index) => [color, index]));

function compareAddedDesc(left: WardrobeApiItem, right: WardrobeApiItem): number {
  const leftAdded = Date.parse(left.added_to_closet_at ?? left.created_at) || 0;
  const rightAdded = Date.parse(right.added_to_closet_at ?? right.created_at) || 0;
  if (leftAdded !== rightAdded) return rightAdded - leftAdded;

  const leftCreated = Date.parse(left.created_at) || 0;
  const rightCreated = Date.parse(right.created_at) || 0;
  if (leftCreated !== rightCreated) return rightCreated - leftCreated;
  return left.id.localeCompare(right.id);
}

function compareColorName(left: WardrobeApiItem, right: WardrobeApiItem): number {
  const unknownRank = COLORS.length;
  const leftColor = colorRank.get(left.color) ?? unknownRank;
  const rightColor = colorRank.get(right.color) ?? unknownRank;
  if (leftColor !== rightColor) return leftColor - rightColor;

  const byName = itemDisplayName(left).localeCompare(itemDisplayName(right), 'ko-KR');
  if (byName !== 0) return byName;
  return compareAddedDesc(left, right);
}

function sortItems(items: WardrobeApiItem[], itemSort: WardrobeItemSort): WardrobeApiItem[] {
  return [...items].sort(itemSort === 'COLOR_NAME_ASC' ? compareColorName : compareAddedDesc);
}

function matchesFilters(item: WardrobeApiItem, filters: WardrobeSectionFilters): boolean {
  const categoryMatched =
    filters.selectedCategories.length === 0 ||
    filters.selectedCategories.includes(item.category_large) ||
    item.custom_categories.some((category) =>
      filters.selectedCategories.includes(category.name),
    );
  if (!categoryMatched) return false;

  const query = filters.query.trim();
  if (!query) return true;
  return itemDisplayName(item).includes(query) || item.category_large.includes(query);
}

/**
 * 서버 목록 순서와 무관하게 개인 옷장의 섹션과 섹션 내부 순서를 결정한다.
 * 사용자 카테고리 그룹은 다대다 소속을 그대로 보여주므로 같은 옷이 여러 섹션에 나올 수 있다.
 */
export function buildWardrobeSections(
  items: WardrobeApiItem[],
  filters: WardrobeSectionFilters,
  groupMode: WardrobeGroupMode,
  itemSort: WardrobeItemSort,
): WardrobeSection[] {
  const filtered = items.filter((item) => matchesFilters(item, filters));

  if (groupMode === 'SYSTEM_CATEGORY') {
    return filters.systemCategoryOrder.flatMap((category) => {
      const sectionItems = filtered.filter((item) => item.category_large === category);
      return sectionItems.length > 0
        ? [{ id: `system:${category}`, title: category, items: sortItems(sectionItems, itemSort) }]
        : [];
    });
  }

  const categorySections = filters.customCategoryOrder.flatMap((category) => {
    const sectionItems = filtered.filter((item) =>
      item.custom_categories.some((entry) => entry.id === category.id),
    );
    return sectionItems.length > 0
      ? [{ id: category.id, title: category.name, items: sortItems(sectionItems, itemSort) }]
      : [];
  });
  const uncategorized = filtered.filter((item) => item.custom_categories.length === 0);

  return uncategorized.length > 0
    ? [
        ...categorySections,
        {
          id: UNCATEGORIZED_SECTION_ID,
          title: '미분류',
          items: sortItems(uncategorized, itemSort),
        },
      ]
    : categorySections;
}

/** 사용자 카테고리 그룹의 중복 카드와 무관한 실제 옷 개수. */
export function uniqueWardrobeItemCount(sections: WardrobeSection[]): number {
  return new Set(sections.flatMap((section) => section.items.map((item) => item.id))).size;
}

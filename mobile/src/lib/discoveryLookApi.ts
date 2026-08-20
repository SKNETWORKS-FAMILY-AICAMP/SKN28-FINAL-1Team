import { LookbookEndpoints } from '@/constants/config';
import { API_BASE_URL } from '@/constants/config';
import { api } from '@/lib/apiClient';

export type ShoppingProductDto = {
  id: string;
  /** 서버의 서비스 대분류. 누락된 구버전 응답은 슬롯 검증에서 제외한다. */
  category_large?: string;
  name: string;
  brand: string;
  image: string;
  price: number;
  mall_name: string;
  link: string;
};

export type DiscoveryLookItemDto = ShoppingProductDto & {
  slot: string;
  category_small: string;
  similar_products: ShoppingProductDto[];
};

export type DiscoveryLookDto = {
  id: string;
  gender: LookGender;
  title: string;
  subtitle: string;
  image: string;
  tags: string[];
  total_price: number;
  items: DiscoveryLookItemDto[];
  reasons: string[];
};

export type LookGender = 'WOMAN' | 'MAN';
export type LookGenderFilter = 'ALL' | LookGender;

type DiscoveryLookPage = {
  count: number;
  next_offset: number | null;
  results: DiscoveryLookDto[];
};

export function getDiscoveryLooks(
  query = '',
  tag = '',
  gender: LookGenderFilter = 'ALL',
): Promise<DiscoveryLookPage> {
  const params = new URLSearchParams({ limit: '50' });
  if (gender !== 'ALL') params.set('gender', gender);
  if (query.trim()) params.set('query', query.trim());
  if (tag.trim()) params.set('tag', tag.trim());
  return api.get<DiscoveryLookPage>(`${LookbookEndpoints.discover}?${params}`, { auth: false })
    .then((page) => ({ ...page, results: page.results.map(normalizeLook) }));
}

export function getDiscoveryLook(id: string): Promise<DiscoveryLookDto> {
  return api.get<DiscoveryLookDto>(LookbookEndpoints.discoverDetail(id), { auth: false })
    .then(normalizeLook);
}

function normalizeLook(look: DiscoveryLookDto): DiscoveryLookDto {
  return { ...look, image: look.image.startsWith('/') ? `${API_BASE_URL}${look.image}` : look.image };
}

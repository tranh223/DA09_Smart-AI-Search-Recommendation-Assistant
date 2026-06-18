import { otaGet } from './otaApi';

// ---- Kiểu dữ liệu chuẩn hoá dùng trong UI ----

export interface HotelImage {
  url: string;
  is_primary?: boolean;
}

export interface HotelAmenity {
  name: string;
  category?: string;
}

export interface Hotel {
  id: number;
  name: string;
  property_type?: string;
  accommodation_type?: string;
  star_rating?: number;
  is_luxury?: boolean;
  review_score?: number;
  review_count?: number;
  address?: string;
  city?: string;
  area?: string;
  country?: string;
  description?: string;
  min_price?: number; // VND
  images: HotelImage[];
  amenities?: HotelAmenity[];
}

export interface HotelListResult {
  hotels: Hotel[];
  total: number;
  page: number;
  limit: number;
}

export interface HotelListParams {
  city?: string;
  star_rating_min?: number;
  price_min?: number;
  price_max?: number;
  sort_by?: string;
  page?: number;
  limit?: number;
}

// Gợi ý từ VinBot, dạng truy vấn API thật để hiển thị/lọc như danh sách thường.
export interface RecoQuery {
  label: string;
  params: HotelListParams;
  hotels?: Hotel[];
}

// ---- Trích ảnh từ một bản ghi bất kỳ (API có thể trả nhiều dạng) ----

export function extractImages(raw: any): HotelImage[] {
  const out: HotelImage[] = [];
  const arr = raw?.images ?? raw?.hotel_images ?? raw?.photos;
  if (Array.isArray(arr)) {
    for (const it of arr) {
      if (typeof it === 'string') out.push({ url: it });
      else if (it?.url) out.push({ url: it.url, is_primary: !!it.is_primary });
      else if (it?.image_url) out.push({ url: it.image_url, is_primary: !!it.is_primary });
    }
  }
  // Một số endpoint chỉ trả 1 ảnh đại diện
  const single =
    raw?.primary_image ?? raw?.image_url ?? raw?.thumbnail ?? raw?.cover_image;
  if (typeof single === 'string' && !out.some((i) => i.url === single)) {
    out.unshift({ url: single, is_primary: true });
  }
  return out;
}

function toNumber(v: any): number | undefined {
  if (v === null || v === undefined || v === '') return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

function minRoomPrice(rooms: any): number | undefined {
  if (!Array.isArray(rooms)) return undefined;
  const prices = rooms.map((r) => toNumber(r?.price)).filter((p): p is number => p != null && p > 0);
  return prices.length ? Math.min(...prices) : undefined;
}

function normalizeAmenities(raw: any): HotelAmenity[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  return raw
    .map((a) => (typeof a === 'string' ? { name: a } : { name: a?.name, category: a?.category_name ?? a?.category }))
    .filter((a) => a.name);
}

function normalizeHotel(raw: any): Hotel {
  return {
    id: raw.id ?? raw.hotel_id,
    name: raw.name ?? 'Khách sạn',
    property_type: raw.property_type,
    accommodation_type: raw.accommodation_type,
    star_rating: toNumber(raw.star_rating),
    is_luxury: !!raw.is_luxury,
    review_score: toNumber(raw.review_score),
    review_count: toNumber(raw.review_count),
    address: raw.address,
    city: raw.city,
    area: raw.area,
    country: raw.country,
    description: raw.description,
    min_price:
      toNumber(raw.min_price ?? raw.min_room_price ?? raw.price_min ?? raw.price) ??
      minRoomPrice(raw.rooms),
    images: extractImages(raw),
    amenities: normalizeAmenities(raw.amenities),
  };
}

// API có thể bọc list theo nhiều cách khác nhau -> chuẩn hoá về 1 dạng.
function unwrapList(raw: any): { items: any[]; total?: number; page?: number; limit?: number } {
  if (Array.isArray(raw)) return { items: raw };
  const items = raw?.data ?? raw?.items ?? raw?.hotels ?? raw?.results ?? [];
  const meta = raw?.pagination ?? raw?.meta ?? raw;
  return {
    items: Array.isArray(items) ? items : [],
    total: toNumber(meta?.total ?? meta?.total_count ?? meta?.count),
    page: toNumber(meta?.page),
    limit: toNumber(meta?.limit ?? meta?.per_page),
  };
}

// ---- API calls ----

export async function listHotels(params: HotelListParams = {}): Promise<HotelListResult> {
  const raw = await otaGet<any>('/api/hotels', { limit: 12, ...params });
  const { items, total, page, limit } = unwrapList(raw);
  const hotels = items.map(normalizeHotel);
  return {
    hotels,
    total: total ?? hotels.length,
    page: page ?? params.page ?? 1,
    limit: limit ?? params.limit ?? 12,
  };
}

export async function getHotel(id: number): Promise<Hotel> {
  const raw = await otaGet<any>(`/api/hotels/${id}`);
  // detail có thể nằm trong { data: {...} }
  const obj = raw?.data && !Array.isArray(raw.data) ? raw.data : raw;
  return normalizeHotel(obj);
}

export async function getHotelImages(id: number): Promise<HotelImage[]> {
  const raw = await otaGet<any>(`/api/hotels/${id}/images`);
  const { items } = unwrapList(raw);
  const imgs: HotelImage[] = [];
  for (const it of items) {
    if (typeof it === 'string') imgs.push({ url: it });
    else if (it?.url) imgs.push({ url: it.url, is_primary: !!it.is_primary });
    else if (it?.image_url) imgs.push({ url: it.image_url, is_primary: !!it.is_primary });
  }
  return imgs;
}

// ---- Helpers hiển thị ----

export function formatPrice(vnd?: number): string {
  if (!vnd || vnd <= 0) return 'Liên hệ';
  if (vnd >= 1_000_000) {
    const tr = vnd / 1_000_000;
    return `từ ${tr.toFixed(tr % 1 === 0 ? 0 : 1)}tr₫`;
  }
  return `từ ${vnd.toLocaleString('vi-VN')}₫`;
}

export function primaryImage(h: Hotel): string | undefined {
  return (h.images.find((i) => i.is_primary) ?? h.images[0])?.url;
}

/** Core beer record returned from the API (beer_info_view). */
export interface Beer {
  id: string;
  url: string;
  name: string;
  price: number | string | null;
  image: string | null;
  shop: string;
  stock_status: string | null;
  last_seen: string | null;

  // Gemini-extracted fields
  product_type: 'beer' | 'set' | 'glass' | 'other' | null;

  // Untappd-enriched fields
  untappd_url: string | null;
  untappd_image: string | null;
  untappd_brewery_name: string | null;
  untappd_beer_name: string | null;
  untappd_style: string | null;
  untappd_abv: number | null;
  untappd_ibu: number | null;
  untappd_rating: number | null;
  untappd_rating_count: number | null;

  // Brewery details
  brewery_logo: string | null;
  brewery_location: string | null;
  brewery_type: string | null;
}

/** Pagination metadata from the API. */
export interface PaginationInfo {
  total: number;
  totalPages: number;
  page: number;
  limit: number;
}

/** API response shape for /api/beers. */
export interface BeersApiResponse {
  beers: Beer[];
  pagination: PaginationInfo;
  shopCounts: Record<string, number>;
}

/** Multi-select dropdown option. */
export interface SelectOption {
  value: string;
  label: string;
  flag?: string;
  count?: number;
}

/** Brewery option returned by /api/breweries. */
export interface BreweryOption {
  name: string;
  flag?: string;
}

/** Style option returned by /api/styles. */
export interface StyleOption {
  style: string;
  count: number;
}

/** Filter state object. */
export interface FilterState {
  min_abv: string;
  max_abv: string;
  min_ibu: string;
  max_ibu: string;
  min_rating: string;
  stock_filter: string;
  untappd_status: string;
  shop: string;
  brewery_filter: string;
  style_filter: string;
  set_mode: string;
  product_type?: string;
}

/** Grouped beer record for the /grouped view. */
export interface GroupedBeer {
  untappd_url: string | null;
  beer_name: string;
  beer_image: string | null;
  style: string | null;
  abv: number | null;
  ibu: number | null;
  rating: number | null;
  rating_count: number | null;
  brewery_name: string | null;
  brewery_logo: string | null;
  brewery_location: string | null;
  brewery_type: string | null;
  untappd_updated_at: string | null;
  is_set: boolean | null;
  product_type: string | null;
  items: {
    shop: string;
    price: number | string | null;
    price_value: number | null;
    url: string;
    stock_status: string | null;
    last_seen: string | null;
    first_seen: string | null;
    image: string | null;
  }[];
  min_price: number;
  max_price: number;
  newest_seen: string;
}

/** API response shape for /api/grouped-beers. */
export interface GroupedBeersApiResponse {
  groups: GroupedBeer[];
  pagination: PaginationInfo;
  shopCounts: Record<string, number>;
}

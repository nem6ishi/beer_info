import { useCallback, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import useSWR, { preload } from 'swr';
import { toThumbnailUrl } from '../components/utils/imageUtils';

export interface PaginationData {
    totalPages: number;
    total: number;
}

interface UseBeerDataOptions<TData, TResponse> {
    initialData: TResponse;
    endpoint: string;
    dataKey: keyof TResponse;
}

const fetcher = async (url: string) => {
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error('Refresh failed');
    }
    return res.json();
};

export function useBeerData<TData, TResponse extends { pagination: PaginationData, shopCounts: Record<string, number>, generatedAt?: number }>({
    initialData,
    endpoint,
    dataKey
}: UseBeerDataOptions<TData, TResponse>) {
    const searchParams = useSearchParams();
    const paramsStr = searchParams.toString();
    const swrKey = `${endpoint}${paramsStr ? `?${paramsStr}` : ''}`;

    // Condition for revalidateOnMount:
    // Only revalidate immediately if initial parameters exist (user directly visited filtered URL)
    // or if initialData is stale (> 30s old). Fresh SSR initialData needs no immediate refetch.
    const isInitialParams = !paramsStr;
    const isFresh = initialData?.generatedAt ? (Date.now() - initialData.generatedAt < 30000) : false;
    const shouldRevalidateOnMount = !isInitialParams || !isFresh;

    const { data: responseData, error: swrError, isValidating, mutate } = useSWR<TResponse>(
        swrKey,
        fetcher,
        {
            fallbackData: !paramsStr ? initialData : undefined,
            revalidateOnMount: shouldRevalidateOnMount,
            revalidateOnFocus: false,
            keepPreviousData: true,
            shouldRetryOnError: false
        }
    );

    const currentData = responseData || initialData;

    const data = (currentData[dataKey] as unknown as TData);
    const shopCounts = currentData.shopCounts || {};
    const totalPages = currentData.pagination?.totalPages || 1;
    const totalItems = currentData.pagination?.total || 0;
    const loading = isValidating && !responseData;
    const error = swrError ? (swrError.message || 'Refresh failed') : null;

    // Helper to generate the URL for a specific page with the current query parameters
    const getPageUrl = useCallback((targetPage: number) => {
        const params = new URLSearchParams(searchParams.toString());
        if (targetPage <= 1) {
            params.delete('page');
        } else {
            params.set('page', targetPage.toString());
        }
        const qs = params.toString();
        return `${endpoint}${qs ? `?${qs}` : ''}`;
    }, [endpoint, searchParams]);

    // Preload a specific page and optionally its images
    const preloadPage = useCallback((targetPage: number) => {
        if (targetPage < 1 || targetPage > totalPages) return;
        const targetUrl = getPageUrl(targetPage);
        preload(targetUrl, fetcher).then((res: any) => {
            // Warm up first 5 thumbnails in browser cache
            if (typeof window !== 'undefined' && res) {
                const items = res[dataKey] as any[];
                if (Array.isArray(items)) {
                    items.slice(0, 5).forEach((item: any) => {
                        const imgUrl = item.image || item.beer_image || item.untappd_image;
                        if (imgUrl) {
                            const thumb = toThumbnailUrl(imgUrl);
                            if (thumb) {
                                const img = new window.Image();
                                img.src = thumb;
                            }
                        }
                    });
                }
            }
        }).catch(() => {
            // Preload failure is harmless; ignored
        });
    }, [getPageUrl, totalPages, dataKey]);

    // Idle-prefetch next page (e.g. page + 1)
    useEffect(() => {
        const currentPage = parseInt(searchParams.get('page') || '1', 10);
        if (currentPage < totalPages) {
            const timer = setTimeout(() => {
                preloadPage(currentPage + 1);
            }, 1200); // 1.2s debounce to give current page priority

            return () => clearTimeout(timer);
        }
    }, [searchParams, totalPages, preloadPage]);

    const fetchData = useCallback(async () => {
        const sep = swrKey.includes('?') ? '&' : '?';
        const bypassUrl = `${swrKey}${sep}_t=${Date.now()}`;
        const freshData = await fetcher(bypassUrl);
        await mutate(freshData, false);
    }, [swrKey, mutate]);

    return {
        data,
        shopCounts,
        loading,
        isValidating,
        error,
        totalPages,
        totalItems,
        fetchData,
        preloadPage
    };
}

import { useState, useCallback, useRef } from 'react';
import { useSearchParams } from 'next/navigation';

export interface PaginationData {
    totalPages: number;
    total: number;
}

interface UseBeerDataOptions<TData, TResponse> {
    initialData: TResponse;
    endpoint: string;
    dataKey: keyof TResponse;
}

export function useBeerData<TData, TResponse extends { pagination: PaginationData, shopCounts: Record<string, number> }>({
    initialData,
    endpoint,
    dataKey
}: UseBeerDataOptions<TData, TResponse>) {
    const searchParams = useSearchParams();

    const [data, setData] = useState<TData>(initialData[dataKey] as unknown as TData);
    const [shopCounts, setShopCounts] = useState<Record<string, number>>(initialData.shopCounts);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [totalPages, setTotalPages] = useState(initialData.pagination.totalPages);
    const [totalItems, setTotalItems] = useState(initialData.pagination.total);

    const abortControllerRef = useRef<AbortController | null>(null);

    const fetchData = useCallback(async () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        const controller = new AbortController();
        abortControllerRef.current = controller;

        setLoading(true);
        try {
            const params = new URLSearchParams(searchParams.toString());
            const res = await fetch(`${endpoint}?${params.toString()}`, { signal: controller.signal });
            const responseData: TResponse = await res.json();
            
            setData(responseData[dataKey] as unknown as TData);
            setShopCounts(responseData.shopCounts || {});
            setTotalPages(responseData.pagination.totalPages);
            setTotalItems(responseData.pagination.total);
            setError(null);
        } catch (err: any) {
            if (err.name !== 'AbortError') {
                setError('Refresh failed');
            }
        } finally {
            if (abortControllerRef.current === controller) {
                setLoading(false);
            }
        }
    }, [searchParams, endpoint, dataKey]);

    const syncDataFromInitial = useCallback(() => {
        setData(initialData[dataKey] as unknown as TData);
        setTotalPages(initialData.pagination.totalPages);
        setTotalItems(initialData.pagination.total);
        setShopCounts(initialData.shopCounts);
    }, [initialData, dataKey]);

    return {
        data,
        shopCounts,
        loading,
        error,
        totalPages,
        totalItems,
        fetchData,
        syncDataFromInitial
    };
}

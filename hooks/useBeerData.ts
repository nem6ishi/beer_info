import { useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import useSWR from 'swr';

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

export function useBeerData<TData, TResponse extends { pagination: PaginationData, shopCounts: Record<string, number> }>({
    initialData,
    endpoint,
    dataKey
}: UseBeerDataOptions<TData, TResponse>) {
    const searchParams = useSearchParams();
    const paramsStr = searchParams.toString();
    const swrKey = `${endpoint}${paramsStr ? `?${paramsStr}` : ''}`;

    const { data: responseData, error: swrError, isValidating, mutate } = useSWR<TResponse>(
        swrKey,
        fetcher,
        {
            fallbackData: !paramsStr ? initialData : undefined,
            revalidateOnFocus: false,
            keepPreviousData: true
        }
    );

    const currentData = responseData || initialData;

    const data = (currentData[dataKey] as unknown as TData);
    const shopCounts = currentData.shopCounts || {};
    const totalPages = currentData.pagination?.totalPages || 1;
    const totalItems = currentData.pagination?.total || 0;
    const loading = isValidating && !responseData;
    const error = swrError ? (swrError.message || 'Refresh failed') : null;

    const fetchData = useCallback(async () => {
        await mutate();
    }, [mutate]);

    const syncDataFromInitial = useCallback(() => {
        mutate(initialData, false);
    }, [mutate, initialData]);

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


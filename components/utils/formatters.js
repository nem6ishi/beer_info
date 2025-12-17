export const formatPrice = (price) => {
    if (!price) return '¥-';
    // Handle both number and string inputs (e.g. "¥1,200")
    const num = typeof price === 'number' ? price : parseInt(price.replace(/[^0-9]/g, ''), 10);
    if (isNaN(num)) return price;
    return `¥${num.toLocaleString()}`;
};

export const formatSimpleDate = (isoString) => {
    if (!isoString) return '-';
    try {
        // Safari friendly date parsing (replace space with T for ISO compliance if needed)
        const date = new Date(isoString.replace(' ', 'T'));
        if (isNaN(date.getTime())) return '-';
        return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
    } catch (e) { return '-'; }
};

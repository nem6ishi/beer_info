export const formatPrice = (priceStr) => {
    // "1,460円(税込1,606円)" -> 1606
    // "1,606円" -> 1606
    let priceNum = priceStr;

    const taxMatch = priceStr.match(/税込([\d,]+)円/);
    if (taxMatch) {
        priceNum = taxMatch[1];
    } else {
        const simpleMatch = priceStr.match(/([\d,]+)円/);
        if (simpleMatch) priceNum = simpleMatch[1];
    }

    // Ensure comma removal for number parsing if needed, but here we just return string formatted
    return `¥${priceNum}`;
};

export const formatTime = (timestamp) => {
    if (!timestamp) return { date: '-', time: '' };

    try {
        // Try to parse as Date (handles ISO format from Supabase)
        const date = new Date(timestamp);
        if (!isNaN(date.getTime())) {
            // Format as YYYY/MM/DD
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return {
                date: `${year}/${month}/${day}`,
                time: ''
            };
        }
    } catch (e) {
        // Fall through to legacy format
    }

    // Legacy format: "YYYY/MM/DD HH:mm:ss"
    const parts = timestamp.split(' ');
    if (parts.length < 2) return { date: timestamp, time: '' };

    return {
        date: parts[0],
        time: parts[1].substring(0, 5) // HH:mm
    };
};

export const getSortableTime = (beer) => {
    if (beer.first_seen) {
        return new Date(beer.first_seen).getTime();
    }
    // Fallback to image timestamp if available
    const timeMatch = beer.image?.match(/cmsp_timestamp=(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})/);
    if (timeMatch) {
        return parseInt(timeMatch[1] + timeMatch[2] + timeMatch[3] + timeMatch[4] + timeMatch[5], 10);
    }
    return 0;
};

export const debounce = (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
};

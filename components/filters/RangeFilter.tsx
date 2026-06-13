import React from 'react';

interface RangeFilterProps {
    minPlaceholder?: string;
    maxPlaceholder?: string;
    minValue: string;
    maxValue?: string;
    onMinChange: (value: string) => void;
    onMaxChange?: (value: string) => void;
    step?: string;
    showMax?: boolean;
}

export default function RangeFilter({
    minPlaceholder = "Min",
    maxPlaceholder = "Max",
    minValue,
    maxValue = "",
    onMinChange,
    onMaxChange,
    step,
    showMax = true
}: RangeFilterProps) {
    if (!showMax) {
        return (
            <input
                type="number"
                step={step}
                className="filter-input"
                placeholder={minPlaceholder}
                value={minValue}
                onChange={(e) => onMinChange(e.target.value)}
            />
        );
    }

    return (
        <div className="input-range-group">
            <input
                type="number"
                step={step}
                className="filter-input"
                placeholder={minPlaceholder}
                value={minValue}
                onChange={(e) => onMinChange(e.target.value)}
            />
            <span>-</span>
            <input
                type="number"
                step={step}
                className="filter-input"
                placeholder={maxPlaceholder}
                value={maxValue}
                onChange={(e) => onMaxChange?.(e.target.value)}
            />
        </div>
    );
}

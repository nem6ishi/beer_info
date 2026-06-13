import React, { ChangeEvent, ReactNode } from 'react';

interface TextFilterProps {
    value: string;
    onChange: (e: ChangeEvent<HTMLInputElement>) => void;
    placeholder?: string;
    className?: string;
    ariaLabel?: string;
    icon?: ReactNode;
}

export default function TextFilter({
    value,
    onChange,
    placeholder = "Search...",
    className = "search-bar",
    ariaLabel = "Search",
    icon
}: TextFilterProps) {
    return (
        <div className={className}>
            {icon}
            <input
                type="text"
                placeholder={placeholder}
                value={value}
                onChange={onChange}
                aria-label={ariaLabel}
            />
        </div>
    );
}

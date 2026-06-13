import React, { ReactNode } from 'react';

interface FilterSectionProps {
    label?: ReactNode;
    children: ReactNode;
    className?: string;
    htmlFor?: string;
}

export default function FilterSection({
    label,
    children,
    className = "filter-group-main",
    htmlFor
}: FilterSectionProps) {
    const isMainGroup = className.includes('filter-group-main');
    
    return (
        <div className={className}>
            {label && (
                <label htmlFor={htmlFor} className={isMainGroup ? 'sort-label' : undefined}>
                    {label}
                </label>
            )}
            {children}
        </div>
    );
}

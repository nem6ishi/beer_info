import { useState, useRef, useEffect, useMemo, useDeferredValue } from 'react'
import type { SelectOption } from '../types/beer'

interface MultiSelectDropdownProps {
    options: SelectOption[];
    selectedValues: string[];
    onChange: (values: string[]) => void;
    placeholder: string;
    searchable?: boolean;
}

const collator = new Intl.Collator('ja', { numeric: true, sensitivity: 'base' });
const DISPLAY_LIMIT = 150;

export default function MultiSelectDropdown({ options, selectedValues, onChange, placeholder, searchable = false }: MultiSelectDropdownProps) {
    const [isOpen, setIsOpen] = useState(false)
    const [searchTerm, setSearchTerm] = useState('')
    const deferredSearchTerm = useDeferredValue(searchTerm)
    const containerRef = useRef<HTMLDivElement>(null)

    // Close on click outside
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [containerRef]);

    const selectedSet = useMemo(() => new Set(selectedValues), [selectedValues]);

    const handleToggle = (value: string) => {
        const newValues = selectedSet.has(value)
            ? selectedValues.filter(v => v !== value)
            : [...selectedValues, value]
        onChange(newValues)
    }

    // Filter and sort options: selected items first, then alphabetically using fast Intl.Collator
    const filteredAndSortedOptions = useMemo(() => {
        const term = deferredSearchTerm.trim().toLowerCase();
        const filtered = (searchable && term)
            ? options.filter(opt => {
                return opt.label.toLowerCase().includes(term) || (opt.searchStr && opt.searchStr.toLowerCase().includes(term));
            })
            : options;

        return [...filtered].sort((a, b) => {
            const aSelected = selectedSet.has(a.value);
            const bSelected = selectedSet.has(b.value);

            // Selected items first
            if (aSelected && !bSelected) return -1;
            if (!aSelected && bSelected) return 1;

            // Otherwise, sort alphabetically
            return collator.compare(a.label, b.label);
        });
    }, [options, deferredSearchTerm, searchable, selectedSet]);

    const visibleOptions = useMemo(() => {
        return filteredAndSortedOptions.slice(0, DISPLAY_LIMIT);
    }, [filteredAndSortedOptions]);

    const remainingCount = filteredAndSortedOptions.length - visibleOptions.length;

    const getDisplayLabel = (): string => {
        if (selectedValues.length === 0) return placeholder
        if (selectedValues.length === 1) return selectedValues[0]
        return `${selectedValues.length} selected`
    }

    return (
        <div className="multi-select-container" ref={containerRef}>
            <button
                className={`multi-select-trigger ${isOpen ? 'active' : ''}`}
                onClick={() => setIsOpen(!isOpen)}
                type="button"
            >
                <span className="truncate">{getDisplayLabel()}</span>
                <span className="arrow">▼</span>
            </button>

            {isOpen && (
                <div className="multi-select-dropdown">
                    {searchable && (
                        <div className="multi-select-search">
                            <input
                                type="text"
                                placeholder="Search..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                autoFocus
                            />
                        </div>
                    )}
                    <div className="multi-select-options">
                        {visibleOptions.length > 0 ? (
                            <>
                                {visibleOptions.map((option) => (
                                    <label key={option.value} className="multi-select-option">
                                        <input
                                            type="checkbox"
                                            checked={selectedSet.has(option.value)}
                                            onChange={() => handleToggle(option.value)}
                                        />
                                        <span>{option.flag && <span style={{ marginRight: '8px' }}>{option.flag}</span>}{option.label}</span>
                                    </label>
                                ))}
                                {remainingCount > 0 && (
                                    <div 
                                        style={{ 
                                            padding: '8px 12px', 
                                            fontSize: '11px', 
                                            color: '#888', 
                                            textAlign: 'center', 
                                            background: '#f8f8f8', 
                                            borderTop: '1px solid #eee' 
                                        }}
                                    >
                                        他 {remainingCount.toLocaleString()} 件（キーワードで絞り込めます）
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className="no-options">No options</div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}

import { useState, useRef, useEffect } from 'react'

export default function MultiSelectDropdown({ options, selectedValues, onChange, placeholder, searchable = false }) {
    const [isOpen, setIsOpen] = useState(false)
    const [searchTerm, setSearchTerm] = useState('')
    const containerRef = useRef(null)

    // Close on click outside
    useEffect(() => {
        function handleClickOutside(event) {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setIsOpen(false)
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [containerRef]);

    const handleToggle = (value) => {
        const newValues = selectedValues.includes(value)
            ? selectedValues.filter(v => v !== value)
            : [...selectedValues, value]
        onChange(newValues)
    }

    const filteredOptions = searchable
        ? options.filter(opt => opt.label.toLowerCase().includes(searchTerm.toLowerCase()))
        : options

    const getDisplayLabel = () => {
        if (selectedValues.length === 0) return placeholder
        if (selectedValues.length === 1) return selectedValues[0] // or map to label
        return `${selectedValues.length} selected`
    }

    return (
        <div className="multi-select-container" ref={containerRef}>
            <button
                className={`multi-select-trigger ${isOpen ? 'active' : ''}`}
                onClick={() => setIsOpen(!isOpen)}
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
                        {filteredOptions.length > 0 ? (
                            filteredOptions.map((option) => (
                                <label key={option.value} className="multi-select-option">
                                    <input
                                        type="checkbox"
                                        checked={selectedValues.includes(option.value)}
                                        onChange={() => handleToggle(option.value)}
                                    />
                                    <span>{option.label}</span>
                                </label>
                            ))
                        ) : (
                            <div className="no-options">No options</div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}

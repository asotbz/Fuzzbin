import './SourceComparison.css'

export interface ComparisonField {
  key: string
  label: string
  imvdbValue: string | null
  discogsValue: string | null
}

interface SourceComparisonProps {
  fields: ComparisonField[]
  onFieldSelect: (fieldKey: string, source: 'imvdb' | 'discogs') => void
  selectedFields: Record<string, 'imvdb' | 'discogs'>
}

export default function SourceComparison({
  fields,
  onFieldSelect,
  selectedFields
}: SourceComparisonProps) {
  return (
    <div className="sourceComparison">
      <div className="sourceComparisonHeader">
        <h3 className="sourceComparisonTitle">Compare Sources</h3>
        <p className="sourceComparisonSubtitle">
          Select the best value for each field
        </p>
      </div>

      <div className="sourceComparisonGrid">
        <div className="sourceComparisonHeaderRow">
          <div className="sourceComparisonFieldLabel">Field</div>
          <div className="sourceComparisonSource sourceComparisonSourceImvdb">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
              <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
              <line x1="12" y1="22.08" x2="12" y2="12" />
            </svg>
            <span>IMVDb</span>
          </div>
          <div className="sourceComparisonSource sourceComparisonSourceDiscogs">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="6" />
              <circle cx="12" cy="12" r="2" />
            </svg>
            <span>Discogs</span>
          </div>
        </div>

        {fields.map((field) => {
          const isDifferent = field.imvdbValue !== field.discogsValue
          const selected = selectedFields[field.key]

          return (
            <div
              key={field.key}
              className={`sourceComparisonRow ${isDifferent ? 'sourceComparisonRowDifferent' : ''}`}
            >
              <div className="sourceComparisonFieldLabel">
                {field.label}
                {isDifferent && field.imvdbValue && field.discogsValue && (
                  <span className="sourceComparisonDiffBadge">Different</span>
                )}
              </div>

              <label className={`
                sourceComparisonOption
                ${selected === 'imvdb' ? 'sourceComparisonOptionSelected' : ''}
                ${!field.imvdbValue ? 'sourceComparisonOptionEmpty' : ''}
              `}>
                <input
                  type="radio"
                  name={`field-${field.key}`}
                  value="imvdb"
                  checked={selected === 'imvdb'}
                  onChange={() => onFieldSelect(field.key, 'imvdb')}
                  disabled={!field.imvdbValue}
                />
                <span className="sourceComparisonOptionValue">
                  {field.imvdbValue || <em>No data</em>}
                </span>
              </label>

              <label className={`
                sourceComparisonOption
                ${selected === 'discogs' ? 'sourceComparisonOptionSelected' : ''}
                ${!field.discogsValue ? 'sourceComparisonOptionEmpty' : ''}
              `}>
                <input
                  type="radio"
                  name={`field-${field.key}`}
                  value="discogs"
                  checked={selected === 'discogs'}
                  onChange={() => onFieldSelect(field.key, 'discogs')}
                  disabled={!field.discogsValue}
                />
                <span className="sourceComparisonOptionValue">
                  {field.discogsValue || <em>No data</em>}
                </span>
              </label>
            </div>
          )
        })}
      </div>
    </div>
  )
}

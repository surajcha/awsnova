import { FiExternalLink } from 'react-icons/fi'

export default function CitationCard({ citation }) {
  const source = citation.source_uri || 'Unknown source'
  const fileName = source.split('/').pop() || source

  return (
    <div className="flex items-start gap-2 text-xs bg-slate-900/50 rounded px-2 py-1.5">
      <FiExternalLink className="text-gray-500 mt-0.5 flex-shrink-0" />
      <div>
        <span className="text-gray-400">{fileName}</span>
        {citation.page && (
          <span className="text-gray-600"> • Page {citation.page}</span>
        )}
        {citation.span && (
          <p className="text-gray-500 mt-0.5 italic line-clamp-2">
            "{citation.span}"
          </p>
        )}
      </div>
    </div>
  )
}

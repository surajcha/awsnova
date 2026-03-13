import { FiList, FiChevronDown, FiChevronUp } from 'react-icons/fi'
import { useState } from 'react'
import CitationCard from './CitationCard'

export default function FactsList({ nodes, edges }) {
  const [showAll, setShowAll] = useState(false)

  if (nodes.length === 0 && edges.length === 0) return null

  const displayEdges = showAll ? edges : edges.slice(0, 10)

  // Build label lookup
  const labelMap = {}
  for (const node of nodes) {
    labelMap[node.id] = node.label
  }

  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <FiList className="text-nova-accent" />
        Extracted Facts
      </h2>

      {/* Entity tags */}
      <div className="mb-4">
        <p className="text-sm text-gray-400 mb-2">
          Entities ({nodes.length}):
        </p>
        <div className="flex flex-wrap gap-1.5">
          {nodes.map((node) => (
            <span
              key={node.id}
              className="text-xs px-2 py-1 rounded-full border border-nova-border bg-slate-800/50 text-gray-300"
              title={`Type: ${node.properties?.entity_type || node.type} | Confidence: ${node.confidence}`}
            >
              {node.label}
              <span className="ml-1 text-gray-600">
                ({node.properties?.entity_type || node.type})
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* Relations */}
      <div>
        <p className="text-sm text-gray-400 mb-2">
          Relations ({edges.length}):
        </p>
        <div className="space-y-1.5">
          {displayEdges.map((edge) => (
            <div
              key={edge.id}
              className="flex items-center gap-2 text-sm bg-slate-800/30 rounded-lg px-3 py-2"
            >
              <span className="text-nova-primary font-medium truncate">
                {labelMap[edge.subject_id] || edge.subject_id}
              </span>
              <span className="text-gray-600 text-xs whitespace-nowrap">
                —[{edge.predicate}]→
              </span>
              <span className="text-nova-accent font-medium truncate">
                {labelMap[edge.object_id] || edge.object_id}
              </span>
              <span className="text-gray-700 text-xs ml-auto whitespace-nowrap">
                {(edge.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>

        {edges.length > 10 && (
          <button
            className="mt-3 text-sm text-nova-primary hover:text-indigo-400 flex items-center gap-1"
            onClick={() => setShowAll(!showAll)}
          >
            {showAll ? (
              <>
                <FiChevronUp /> Show less
              </>
            ) : (
              <>
                <FiChevronDown /> Show all {edges.length} relations
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}

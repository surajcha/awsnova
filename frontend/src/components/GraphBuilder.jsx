import { FiZap, FiRefreshCw } from 'react-icons/fi'

export default function GraphBuilder({
  documents,
  stats,
  onBuild,
  onReset,
  loading,
}) {
  const canBuild = documents.length > 0 && !loading

  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <FiZap className="text-nova-accent" />
        Build Knowledge Graph
      </h2>

      <div className="flex gap-3 mb-4">
        <button
          className="btn-primary flex items-center gap-2 flex-1"
          onClick={onBuild}
          disabled={!canBuild}
        >
          {loading ? (
            <>
              <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
              Building Graph...
            </>
          ) : (
            <>
              <FiZap />
              Build Graph
            </>
          )}
        </button>

        {stats && (
          <button
            className="btn-secondary flex items-center gap-2"
            onClick={onReset}
            disabled={loading}
          >
            <FiRefreshCw />
            Reset
          </button>
        )}
      </div>

      {loading && (
        <div className="bg-indigo-950/30 border border-nova-primary/30 rounded-lg p-4">
          <p className="text-sm text-indigo-300">
            Processing S3 documents with Amazon Nova via Bedrock...
          </p>
          <p className="text-xs text-gray-500 mt-1">
            S3 Fetch → Chunking → Entity Extraction → Deduplication → Graph Build
          </p>
          <div className="mt-3 h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div className="h-full bg-nova-primary rounded-full animate-pulse w-2/3" />
          </div>
        </div>
      )}

      {stats && !loading && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-slate-800/50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-nova-primary">
              {stats.node_count}
            </p>
            <p className="text-xs text-gray-500 mt-1">Entities</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-nova-accent">
              {stats.edge_count}
            </p>
            <p className="text-xs text-gray-500 mt-1">Relations</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-emerald-400">
              {stats.document_count ?? documents.length}
            </p>
            <p className="text-xs text-gray-500 mt-1">Documents</p>
          </div>
          {stats.summary && (
            <p className="col-span-3 text-sm text-gray-400 mt-1">
              {stats.summary}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

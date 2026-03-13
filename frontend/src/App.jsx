import { useGraph } from './hooks/useGraph'
import S3KnowledgeBase from './components/FileUpload'
import GraphBuilder from './components/GraphBuilder'
import QueryPanel from './components/QueryPanel'
import GraphVisualization from './components/GraphVisualization'
import FactsList from './components/FactsList'
import { FiAlertCircle, FiX } from 'react-icons/fi'

export default function App() {
  const {
    s3Config,
    setS3Config,
    documents,
    graphData,
    stats,
    queryResult,
    loading,
    error,
    handleLoadDocuments,
    handleBuildGraph,
    handleQuery,
    handleReset,
    setError,
  } = useGraph()

  return (
    <div className="min-h-screen bg-nova-dark">
      {/* Header */}
      <header className="border-b border-nova-border bg-nova-surface/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-nova-primary rounded-lg flex items-center justify-center">
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-100">Nova MKG</h1>
              <p className="text-xs text-gray-500">
                Multimodal Knowledge Graph Builder
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs bg-slate-800 text-gray-400 px-2.5 py-1 rounded-full border border-nova-border">
              Powered by Amazon Nova via Bedrock
            </span>
          </div>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 mt-4">
          <div className="bg-red-950/50 border border-red-800 rounded-lg p-3 flex items-center gap-3">
            <FiAlertCircle className="text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-300 flex-1">{error}</p>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-300"
            >
              <FiX />
            </button>
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left column: S3 Knowledge Base + Build */}
          <div className="space-y-6">
            <S3KnowledgeBase
              documents={documents}
              onLoadDocuments={handleLoadDocuments}
              loading={loading.loadDocs}
              s3Config={s3Config}
              onS3ConfigChange={setS3Config}
            />
            <GraphBuilder
              documents={documents}
              stats={stats}
              onBuild={handleBuildGraph}
              onReset={handleReset}
              loading={loading.build}
            />
          </div>

          {/* Right column: Query */}
          <div className="space-y-6">
            <QueryPanel
              queryResult={queryResult}
              onQuery={handleQuery}
              loading={loading.query}
              stats={stats}
            />
          </div>
        </div>

        {/* Full-width: Graph visualization + Facts */}
        {(graphData.nodes.length > 0 || graphData.edges.length > 0) && (
          <div className="mt-6 space-y-6">
            <GraphVisualization
              nodes={graphData.nodes}
              edges={graphData.edges}
            />
            <FactsList
              nodes={graphData.nodes}
              edges={graphData.edges}
            />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-nova-border mt-12 py-6">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-xs text-gray-600">
            Nova MKG — Built for Amazon Nova Hackathon | Powered by Amazon Bedrock + AWS Lambda + S3
          </p>
        </div>
      </footer>
    </div>
  )
}

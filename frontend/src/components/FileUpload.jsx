import { useState } from 'react'
import { FiDatabase, FiRefreshCw, FiFile } from 'react-icons/fi'

export default function S3KnowledgeBase({ documents, onLoadDocuments, loading, s3Config, onS3ConfigChange }) {
  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <FiDatabase className="text-nova-accent" />
        S3 Knowledge Base
      </h2>

      {/* S3 Configuration */}
      <div className="space-y-3 mb-4">
        <div>
          <label className="text-xs text-gray-400 block mb-1">S3 Bucket Name</label>
          <input
            type="text"
            value={s3Config.bucket}
            onChange={(e) => onS3ConfigChange({ ...s3Config, bucket: e.target.value })}
            className="w-full bg-slate-800 border border-nova-border rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-nova-primary transition"
            placeholder="e.g. my-knowledge-base-bucket"
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 block mb-1">S3 Prefix (optional)</label>
          <input
            type="text"
            value={s3Config.prefix}
            onChange={(e) => onS3ConfigChange({ ...s3Config, prefix: e.target.value })}
            className="w-full bg-slate-800 border border-nova-border rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-nova-primary transition"
            placeholder="e.g. documents/"
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 block mb-1">Lambda Function URL</label>
          <input
            type="text"
            value={s3Config.lambdaUrl}
            onChange={(e) => onS3ConfigChange({ ...s3Config, lambdaUrl: e.target.value })}
            className="w-full bg-slate-800 border border-nova-border rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-nova-primary transition"
            placeholder="e.g. https://xxx.lambda-url.us-east-1.on.aws"
          />
        </div>
      </div>

      <button
        onClick={onLoadDocuments}
        disabled={loading || !s3Config.bucket || !s3Config.lambdaUrl}
        className="w-full flex items-center justify-center gap-2 bg-slate-700 hover:bg-slate-600 text-gray-200 font-medium py-2.5 px-4 rounded-lg border border-nova-border transition disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <div className="animate-spin h-4 w-4 border-2 border-nova-accent border-t-transparent rounded-full" />
            Loading from S3...
          </>
        ) : (
          <>
            <FiRefreshCw />
            Load Documents from S3
          </>
        )}
      </button>

      {documents.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-sm text-gray-400 font-medium">
            S3 Documents ({documents.length}):
          </p>
          <div className="max-h-60 overflow-y-auto space-y-2">
            {documents.map((doc, idx) => (
              <div
                key={doc.key || idx}
                className="flex items-center gap-3 bg-slate-800/50 rounded-lg px-3 py-2"
              >
                <FiDatabase className="text-nova-primary flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200 truncate">{doc.name || doc.key}</p>
                  <p className="text-xs text-gray-500">
                    s3://{doc.bucket}/{doc.key}
                    {doc.size ? ` · ${formatSize(doc.size)}` : ''}
                  </p>
                </div>
                <span className="text-xs bg-cyan-900/50 text-cyan-400 px-2 py-0.5 rounded-full">
                  S3
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

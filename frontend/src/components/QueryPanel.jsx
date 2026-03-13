import { useState } from 'react'
import { FiSearch, FiMessageCircle } from 'react-icons/fi'
import CitationCard from './CitationCard'

export default function QueryPanel({ queryResult, onQuery, loading, stats }) {
  const [question, setQuestion] = useState('')

  const canQuery = question.trim().length > 0 && !loading && stats?.node_count > 0

  const handleSubmit = (e) => {
    e.preventDefault()
    if (canQuery) {
      onQuery(question)
    }
  }

  const sampleQuestions = [
    'What systems depend on Payment Service?',
    'Who owns the Authentication Service?',
    'What are the main components?',
    'Show all dependencies',
  ]

  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <FiMessageCircle className="text-nova-accent" />
        Ask a Question
      </h2>

      <form onSubmit={handleSubmit} className="flex gap-2 mb-4">
        <input
          type="text"
          className="input-field flex-1"
          placeholder={
            stats?.node_count > 0
              ? 'Ask a question about your knowledge graph...'
              : 'Build a graph first to enable queries'
          }
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={!stats?.node_count || loading}
        />
        <button
          type="submit"
          className="btn-primary flex items-center gap-2"
          disabled={!canQuery}
        >
          {loading ? (
            <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
          ) : (
            <FiSearch />
          )}
          Ask
        </button>
      </form>

      {stats?.node_count > 0 && !queryResult && !loading && (
        <div className="mb-4">
          <p className="text-xs text-gray-500 mb-2">Try asking:</p>
          <div className="flex flex-wrap gap-2">
            {sampleQuestions.map((q) => (
              <button
                key={q}
                className="text-xs bg-slate-800/50 hover:bg-slate-700 text-gray-400 hover:text-gray-200 px-3 py-1.5 rounded-full border border-nova-border transition-colors"
                onClick={() => setQuestion(q)}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className="bg-indigo-950/30 border border-nova-primary/30 rounded-lg p-4">
          <p className="text-sm text-indigo-300">
            Reasoning over the knowledge graph with Amazon Nova...
          </p>
        </div>
      )}

      {queryResult && !loading && (
        <div className="space-y-4">
          <div className="bg-slate-800/50 rounded-lg p-4 border-l-4 border-nova-accent">
            <p className="text-gray-200">{queryResult.answer}</p>
          </div>

          {queryResult.items?.length > 0 && (
            <div>
              <p className="text-sm font-medium text-gray-400 mb-2">
                Evidence ({queryResult.items.length} facts):
              </p>
              <div className="space-y-2">
                {queryResult.items.map((item, idx) => (
                  <div
                    key={idx}
                    className="bg-slate-800/30 rounded-lg p-3 border border-nova-border"
                  >
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-nova-primary font-medium">
                        {item.subject}
                      </span>
                      <span className="text-gray-500">—[{item.predicate}]→</span>
                      <span className="text-nova-accent font-medium">
                        {item.object}
                      </span>
                    </div>
                    {item.citations?.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {item.citations.map((cite, cIdx) => (
                          <CitationCard key={cIdx} citation={cite} />
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

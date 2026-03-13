import { useState, useCallback, useEffect } from 'react'
import {
  listS3Documents,
  buildGraph,
  queryGraph,
  getGraphStats,
  resetGraph,
  setLambdaUrl,
} from '../api/client'

export function useGraph() {
  const [s3Config, setS3Config] = useState({
    bucket: '',
    prefix: '',
    lambdaUrl: '',
  })
  const [documents, setDocuments] = useState([])
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] })
  const [stats, setStats] = useState(null)
  const [queryResult, setQueryResult] = useState(null)
  const [loading, setLoading] = useState({
    loadDocs: false,
    build: false,
    query: false,
  })
  const [error, setError] = useState(null)

  // Sync Lambda URL whenever s3Config changes
  useEffect(() => {
    if (s3Config.lambdaUrl) {
      setLambdaUrl(s3Config.lambdaUrl)
    }
  }, [s3Config.lambdaUrl])

  const handleLoadDocuments = useCallback(async () => {
    setLoading((prev) => ({ ...prev, loadDocs: true }))
    setError(null)
    try {
      const docs = await listS3Documents(s3Config.bucket, s3Config.prefix)
      setDocuments(docs)
      return docs
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      throw err
    } finally {
      setLoading((prev) => ({ ...prev, loadDocs: false }))
    }
  }, [s3Config.bucket, s3Config.prefix])

  const handleBuildGraph = useCallback(async () => {
    setLoading((prev) => ({ ...prev, build: true }))
    setError(null)
    try {
      const s3Keys = documents.map((d) => d.key)
      const result = await buildGraph(s3Config.bucket, s3Config.prefix, s3Keys)
      setGraphData({ nodes: result.nodes || [], edges: result.edges || [] })
      setStats({
        node_count: (result.nodes || []).length,
        edge_count: (result.edges || []).length,
        document_count: documents.length,
        summary: result.summary,
      })
      return result
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      throw err
    } finally {
      setLoading((prev) => ({ ...prev, build: false }))
    }
  }, [documents, s3Config.bucket, s3Config.prefix])

  const handleQuery = useCallback(async (question) => {
    setLoading((prev) => ({ ...prev, query: true }))
    setError(null)
    try {
      const result = await queryGraph(question, s3Config.bucket, s3Config.prefix)
      setQueryResult(result)
      return result
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      throw err
    } finally {
      setLoading((prev) => ({ ...prev, query: false }))
    }
  }, [s3Config.bucket, s3Config.prefix])

  const handleReset = useCallback(async () => {
    try {
      await resetGraph()
    } catch {}
    setGraphData({ nodes: [], edges: [] })
    setStats(null)
    setQueryResult(null)
    setDocuments([])
    setError(null)
  }, [])

  const refreshStats = useCallback(async () => {
    try {
      const s = await getGraphStats()
      setStats(s)
    } catch {
      // ignore
    }
  }, [])

  return {
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
    refreshStats,
    setError,
  }
}

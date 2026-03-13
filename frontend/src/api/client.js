import axios from 'axios'

const api = axios.create({
  timeout: 300000, // 5 min timeout for Lambda processing
  headers: { 'Content-Type': 'application/json' },
})

// The Lambda URL is passed from the caller (via s3Config.lambdaUrl in useGraph)
let _lambdaUrl = import.meta.env.VITE_LAMBDA_URL || ''

export function setLambdaUrl(url) {
  _lambdaUrl = (url || '').replace(/\/$/, '')
}

export function getLambdaUrl() {
  return _lambdaUrl
}

export async function listS3Documents(bucket, prefix = '') {
  const { data } = await api.post(`${_lambdaUrl}/list-documents`, {
    bucket,
    prefix,
  })
  return data.documents || []
}

export async function buildGraph(bucket, prefix, s3Keys) {
  const { data } = await api.post(`${_lambdaUrl}/build-graph`, {
    bucket,
    prefix,
    s3_keys: s3Keys,
  })
  return data
}

export async function queryGraph(question, bucket, prefix) {
  const { data } = await api.post(`${_lambdaUrl}/query`, {
    question,
    bucket,
    prefix,
  })
  return data
}

export async function getGraphStats() {
  const { data } = await api.post(`${_lambdaUrl}/graph-stats`)
  return data
}

export async function resetGraph() {
  const { data } = await api.post(`${_lambdaUrl}/reset`)
  return data
}

export default api

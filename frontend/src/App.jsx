import { useState, useEffect } from 'react'
import './App.css'
import ChatPanel from './ChatPanel'

const API_BASE = '/api/v1'

function App() {
  const [file, setFile] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')
  const [results, setResults] = useState(null)
  const [metadata, setMetadata] = useState(null)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [expandedQuotes, setExpandedQuotes] = useState({})

  // Poll status when we have a jobId
  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') {
      return
    }

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/status/${jobId}`)
        if (!response.ok) throw new Error('Failed to fetch status')
        
        const data = await response.json()
        setStatus(data.status)
        setProgress(data.progress || (data.status === 'pending' ? 5 : data.status === 'processing' ? 50 : 0))
        setStage(data.stage || '')
        
        if (data.status === 'completed') {
          clearInterval(interval)
          setProgress(100)
          await fetchResults()
        } else if (data.status === 'failed') {
          clearInterval(interval)
          setError(data.error_message || 'Job processing failed')
        }
      } catch (err) {
        console.error('Status polling error:', err)
        setError(err.message)
        clearInterval(interval)
      }
    }, 1500) // Poll every 1.5 seconds

    return () => clearInterval(interval)
  }, [jobId, status])

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile)
      setError(null)
    } else {
      setError('Please select a PDF file')
      setFile(null)
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setUploading(true)
    setError(null)
    setResults(null)
    setJobId(null)
    setStatus(null)
    setProgress(0)
    setStage('')
    setMetadata(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data = await response.json()
      setJobId(data.job_id)
      setStatus(data.status)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const fetchResults = async () => {
    try {
      const response = await fetch(`${API_BASE}/result/${jobId}`)
      if (!response.ok) throw new Error('Failed to fetch results')
      
      const data = await response.json()
      setResults(data.results)
      
      // Extract metadata from results and backend
      setMetadata({
        filename: data.filename,
        llm_mode: data.llm_mode || 'external',
        model_name: data.model_name || 'gpt-4',
        needs_ocr: data.needs_ocr || false,
        timings_ms: data.timings_ms || null
      })
    } catch (err) {
      setError(err.message)
    }
  }

  const handleReset = () => {
    setFile(null)
    setJobId(null)
    setStatus(null)
    setProgress(0)
    setStage('')
    setResults(null)
    setMetadata(null)
    setError(null)
  }

  const toggleQuotes = (index) => {
    setExpandedQuotes(prev => ({
      ...prev,
      [index]: !prev[index]
    }))
  }

  const getStateColor = (state) => {
    switch(state) {
      case 'Fully Compliant': return '#4ade80'
      case 'Partially Compliant': return '#facc15'
      case 'Non-Compliant': return '#f87171'
      default: return '#9ca3af'
    }
  }

  const getStatusBadgeClass = (status) => {
    switch(status) {
      case 'pending': return 'status-badge status-pending'
      case 'processing': return 'status-badge status-processing'
      case 'completed': return 'status-badge status-completed'
      case 'failed': return 'status-badge status-failed'
      default: return 'status-badge'
    }
  }

  const getStatusLabel = (status) => {
    switch(status) {
      case 'pending': return 'Queued'
      case 'processing': return 'Processing'
      case 'completed': return 'Completed'
      case 'failed': return 'Failed'
      default: return status
    }
  }

  const formatTime = (ms) => {
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const getOverallCompliance = () => {
    if (!results || results.length === 0) return null
    
    const fullyCompliant = results.filter(r => r.compliance_state === 'Fully Compliant').length
    const total = results.length
    const allFullyCompliant = fullyCompliant === total
    
    // Count total quotes and check rationale for removals
    let quotesRemoved = false
    results.forEach(r => {
      if (r.rationale && (r.rationale.includes('quotes removed') || r.rationale.includes('No verifiable'))) {
        quotesRemoved = true
      }
    })
    
    return {
      fullyCompliant,
      total,
      allFullyCompliant,
      quotesRemoved
    }
  }

  const getConfidenceTooltip = (confidence, rationale) => {
    if (confidence >= 95) return null
    
    let reasons = []
    if (confidence < 95 && confidence >= 70) {
      reasons.push('Some criteria may be implied rather than explicit')
    }
    if (rationale.includes('quotes removed')) {
      reasons.push('Some LLM-generated quotes could not be verified in source')
    }
    if (rationale.includes('No verifiable')) {
      reasons.push('No quotes could be verified against source evidence')
    }
    if (confidence < 50) {
      reasons.push('Limited or ambiguous evidence found')
    }
    
    return reasons.length > 0 ? reasons.join('. ') : 'Based on evidence quality and completeness'
  }

  return (
    <div className="app">
      <div className="container">
        <h1>Contract Compliance Analyzer</h1>
        
        {/* Upload Section */}
        <div className="upload-section">
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            disabled={uploading || (status && status !== 'completed' && status !== 'failed')}
          />
          <button
            onClick={handleUpload}
            disabled={!file || uploading || (status && status !== 'completed' && status !== 'failed')}
          >
            {uploading ? 'Uploading...' : 'Analyze Contract'}
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="error">
            <strong>Error:</strong> {error}
            {status === 'failed' && (
              <button className="retry-btn" onClick={handleReset}>Try Again</button>
            )}
          </div>
        )}

        {/* Processing Status Panel - Always show when job exists */}
        {jobId && status && (
          <div className="status-panel">
            <div className="status-header">
              <span className={getStatusBadgeClass(status)}>
                {getStatusLabel(status)}
              </span>
              {status !== 'completed' && status !== 'failed' && (
                <span className="progress-text">{progress}%</span>
              )}
            </div>
            
            {/* Progress Bar - Only show when processing */}
            {status !== 'completed' && status !== 'failed' && (
              <div className="progress-bar-container">
                <div 
                  className="progress-bar-fill" 
                  style={{ width: `${progress}%` }}
                />
              </div>
            )}
            
            {/* Stage Text */}
            {stage && status !== 'completed' && (
              <div className="stage-text">
                {stage}
              </div>
            )}
            
            {/* Timing - Only show when completed */}
            {status === 'completed' && metadata?.timings_ms && (
              <div className="timing-summary">
                ⏱️ Total: {formatTime(metadata.timings_ms.total_ms)} 
                {' '}• LLM: {formatTime(metadata.timings_ms.llm_total_ms)}
                {' '}• Parse: {formatTime(metadata.timings_ms.parse_ms)}
              </div>
            )}
            
            <div className="job-id-small">
              Job ID: {jobId}
            </div>
          </div>
        )}

        {/* Metadata */}
        {metadata && results && (
          <div className="metadata">
            <div className="metadata-line">
              <strong>Document:</strong> {metadata.filename} | 
              <strong> LLM:</strong> {metadata.llm_mode} - {metadata.model_name} | 
              <strong> OCR Needed:</strong> {metadata.needs_ocr ? 'Yes ⚠️' : 'No'}
            </div>
            {metadata.needs_ocr && (
              <div className="metadata-warning">
                Document may need OCR (low text density). Results may have lower confidence.
              </div>
            )}
          </div>
        )}

        {/* Results Table */}
        {results && results.length > 0 && (
          <div className="results">
            <h2>Compliance Results</h2>
            
            {/* Overall Compliance Summary */}
            {(() => {
              const summary = getOverallCompliance()
              return summary && (
                <div className={`compliance-summary ${summary.allFullyCompliant ? 'all-compliant' : 'partial-compliant'}`}>
                  <div className="summary-main">
                    <strong>Overall Compliance:</strong> {' '}
                    {summary.allFullyCompliant ? 'Fully Compliant' : 'Partially Compliant'} ({summary.fullyCompliant}/{summary.total} requirements)
                  </div>
                  {summary.quotesRemoved && (
                    <div className="summary-note">
                      ⚠️ Note: Some AI-generated quotes were removed during validation (not found verbatim in source document)
                    </div>
                  )}
                </div>
              )
            })()}
            
            <table>
              <thead>
                <tr>
                  <th>Question</th>
                  <th>State</th>
                  <th>Confidence</th>
                  <th>Quotes</th>
                  <th>Rationale</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result, index) => (
                  <tr key={index}>
                    <td className="question">{result.compliance_question}</td>
                    <td>
                      <span 
                        className="state-badge"
                        style={{ backgroundColor: getStateColor(result.compliance_state) }}
                      >
                        {result.compliance_state}
                      </span>
                    </td>
                    <td className="confidence">
                      <span 
                        className={result.confidence < 100 ? 'confidence-with-tooltip' : ''}
                        title={getConfidenceTooltip(result.confidence, result.rationale) || ''}
                      >
                        {result.confidence}%
                        {result.confidence < 100 && <span className="info-icon">ⓘ</span>}
                      </span>
                    </td>
                    <td className="quotes">
                      {result.relevant_quotes && result.relevant_quotes.length > 0 ? (
                        <div>
                          <button 
                            className="expand-btn"
                            onClick={() => toggleQuotes(index)}
                          >
                            {expandedQuotes[index] ? '▼' : '▶'} 
                            {result.relevant_quotes.length} quote(s)
                          </button>
                          {expandedQuotes[index] && (
                            <div className="quotes-expanded">
                              {result.relevant_quotes.map((quote, qIdx) => (
                                <div key={qIdx} className="quote-item">
                                  <div className="quote-text">"{quote.text}"</div>
                                  <div className="quote-pages">
                                    Pages {quote.page_start}
                                    {quote.page_end !== quote.page_start && `-${quote.page_end}`}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="no-quotes">No quotes</span>
                      )}
                    </td>
                    <td className="rationale">{result.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Collapsible JSON View */}
            <details className="json-viewer">
              <summary>View JSON Response</summary>
              <pre className="json-content">
                {JSON.stringify(results, null, 2)}
              </pre>
            </details>
          </div>
        )}

        {/* Chat Panel - Only show when job is completed */}
        {status === 'completed' && jobId && (
          <ChatPanel jobId={jobId} />
        )}
      </div>
    </div>
  )
}

export default App

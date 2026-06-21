import { useState, useEffect, useCallback, type FormEvent } from 'react'
import { LayoutDashboard, FileCheck, Save, Download, FileJson, AlertCircle, Maximize2, Loader2, CheckCircle2, Image as ImageIcon, Layers, Upload } from 'lucide-react'
import { parseMetadataResponse, type MetadataResult } from './metadata'
import { canSaveCandidates, candidateSourceFromApi, candidateSourceLabel, type CandidateSource } from './sampleMode'

export interface Candidate {
  candidate_id: string;
  status: string;
  raw_text: string | null;
  label_type: string | null;
  width_mm: number | null;
  height_mm: number | null;
  diameter_mm: number | null;
  ra_value: string | number | null;
  ok_value: string | number | null;
  reference: string | null;
  review_comment: string | null;
  crop_path: string | null;
}

type EditableCandidateField = 'status' | 'raw_text' | 'label_type' | 'width_mm' | 'height_mm' | 'diameter_mm' | 'ra_value' | 'ok_value' | 'reference' | 'review_comment'
type EditableCandidateValue = string | number | null

interface PipelineStatus {
  files: {
    page_image: boolean
    overlay_image: boolean
    candidates_json: boolean
    review_json: boolean
    export_json: boolean
  }
}

function candidateSourceBadgeClass(source: CandidateSource): string {
  if (source === 'sample') return 'bg-amber-100 text-amber-800'
  if (source === 'review') return 'bg-blue-100 text-blue-800'
  return 'bg-slate-100 text-slate-700'
}

function hasCandidateDimensions(candidate: Candidate): boolean {
  return Boolean(
    (candidate.width_mm && candidate.height_mm) ||
    candidate.diameter_mm
  )
}

function formatCandidateDimensions(candidate: Candidate): string {
  if (candidate.width_mm && candidate.height_mm) return `${candidate.width_mm}x${candidate.height_mm}`
  if (candidate.diameter_mm) return `Ø${candidate.diameter_mm}`
  return candidate.label_type ? 'Measurement needs review' : '-'
}

function App() {
  const [activePlan, setActivePlan] = useState<string | null>(null)
  const [plans, setPlans] = useState<string[]>([])
  const [loadingPlans, setLoadingPlans] = useState(true)
  const [selectedImportFile, setSelectedImportFile] = useState<File | null>(null)
  const [importInputKey, setImportInputKey] = useState(0)
  const [isImportingPlan, setIsImportingPlan] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [importMessage, setImportMessage] = useState<string | null>(null)
  
  // Plan-specific states
  const [metadataResult, setMetadataResult] = useState<MetadataResult | null>(null)
  const [imageError, setImageError] = useState(false)
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null)
  const [showOverlay, setShowOverlay] = useState(false)

  // Candidates states
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [loadingCandidates, setLoadingCandidates] = useState(true)
  const [candidateSource, setCandidateSource] = useState<CandidateSource>('raw')
  const [candidateReloadKey, setCandidateReloadKey] = useState(0)
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null)
  const [cropError, setCropError] = useState(false)
  const [isExporting, setIsExporting] = useState<{csv: boolean, json: boolean}>({csv: false, json: false})

  const handlePlanSelection = useCallback((planId: string) => {
    setImageError(false)
    setMetadataResult(null)
    setCandidates([])
    setCandidateSource('raw')
    setPipelineStatus(null)
    setShowOverlay(false)
    setLoadingCandidates(true)
    setSaveSuccess(false)
    setSelectedCandidateId(null)
    setCropError(false)
    setActivePlan(planId)
  }, [])

  const refreshPlans = useCallback(async (selectedPlanId?: string) => {
    const response = await fetch('/api/plans')
    if (!response.ok) throw new Error(`Plans request failed (${response.status})`)
    const data = await response.json()
    const nextPlans = Array.isArray(data.plans) ? data.plans : []

    setPlans(nextPlans)
    if (selectedPlanId && nextPlans.includes(selectedPlanId)) {
      handlePlanSelection(selectedPlanId)
    } else if (nextPlans.length > 0) {
      setActivePlan(currentPlan => currentPlan ?? nextPlans[0])
    }
  }, [handlePlanSelection])

  const handleImportPlan = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedImportFile) return

    setIsImportingPlan(true)
    setImportError(null)
    setImportMessage(null)

    const formData = new FormData()
    formData.append('file', selectedImportFile)

    try {
      const response = await fetch('/api/import/pdf', {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || `Import failed (${response.status})`)
      }
      if (!data.success) {
        throw new Error(data.stderr || 'Pipeline failed for this plan.')
      }

      setSelectedImportFile(null)
      setImportInputKey(key => key + 1)
      setImportMessage(`${data.plan_id} analyzed`)
      await refreshPlans(data.plan_id)
    } catch (error) {
      setImportError(error instanceof Error ? error.message : 'Import failed')
    } finally {
      setIsImportingPlan(false)
    }
  }

  // Fetch available plans on mount
  useEffect(() => {
    refreshPlans()
      .catch(err => console.error("Failed to load plans:", err))
      .finally(() => setLoadingPlans(false))
  }, [refreshPlans])

  // Fetch metadata, candidates and status when activePlan changes
  useEffect(() => {
    if (!activePlan) return
    
    // 1. Fetch metadata
    fetch(`/api/metadata/${activePlan}`)
      .then(res => {
        if (!res.ok) throw new Error(`Metadata request failed (${res.status})`)
        return res.json()
      })
      .then(data => setMetadataResult(parseMetadataResponse(data)))
      .catch(err => {
        console.error("Failed to load metadata:", err)
        setMetadataResult({ kind: 'error', message: err.message })
      })

    // 2. Fetch pipeline status
    fetch(`/api/status/${activePlan}`)
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data) setPipelineStatus(data)
      })
      .catch(err => console.error("Failed to load pipeline status:", err))

    // 3. Fetch candidates (Try reviews first, fallback to raw candidates)
    fetch(`/api/reviews/${activePlan}`)
      .then(res => {
        if (res.ok) return res.json()
        throw new Error('No draft found')
      })
      .then(data => {
        if (data && data.candidates && data.candidates.length > 0) {
          setCandidates(data.candidates)
          setCandidateSource(candidateSourceFromApi(data.source))
          setLoadingCandidates(false)
        } else {
          throw new Error('Empty draft')
        }
      })
      .catch(() => {
        // Fallback to raw candidates
        fetch(`/api/candidates/${activePlan}`)
          .then(res => res.ok ? res.json() : { candidates: [] })
          .then(data => {
            setCandidates(data.candidates || [])
            setCandidateSource(candidateSourceFromApi(data.source))
          })
          .catch(err => console.error("Failed to load candidates:", err))
          .finally(() => setLoadingCandidates(false))
      })

  }, [activePlan, candidateReloadKey])

  const handleSave = async () => {
    if (!activePlan || candidates.length === 0 || !canSaveCandidates(candidateSource)) return
    setIsSaving(true)
    setSaveSuccess(false)
    try {
      const response = await fetch(`/api/reviews/${activePlan}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(candidates),
      })
      if (response.ok) {
        setSaveSuccess(true)
        setTimeout(() => setSaveSuccess(false), 3000)
        // Refresh status to update UI flags
        fetch(`/api/status/${activePlan}`)
          .then(res => res.ok ? res.json() : null)
          .then(data => { if (data) setPipelineStatus(data) })
      } else {
        console.error("Save failed:", await response.text())
      }
    } catch (error) {
      console.error("Save error:", error)
    } finally {
      setIsSaving(false)
    }
  }

  const loadSampleCandidates = async () => {
    setLoadingCandidates(true)
    try {
      const response = await fetch('/api/candidates/sample')
      if (!response.ok) throw new Error(`Sample candidate request failed (${response.status})`)
      const data = await response.json()
      setCandidates(data.candidates || [])
      setCandidateSource('sample')
      setSelectedCandidateId(null)
      setCropError(false)
    } catch (error) {
      console.error('Failed to load sample candidates:', error)
    } finally {
      setLoadingCandidates(false)
    }
  }

  const exitSampleMode = () => {
    setCandidateSource('raw')
    setLoadingCandidates(true)
    setCandidateReloadKey(key => key + 1)
  }

  const handleExport = async (type: 'csv' | 'json') => {
    if (!activePlan || candidates.length === 0) return
    setIsExporting(prev => ({ ...prev, [type]: true }))
    try {
      const response = await fetch(`/api/exports/${type}/${activePlan}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(candidates),
      })
      if (!response.ok) throw new Error("Export failed")
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${activePlan}_verified_openings.${type}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      // Refresh status to update UI flags
      fetch(`/api/status/${activePlan}`)
        .then(res => res.ok ? res.json() : null)
        .then(data => { if (data) setPipelineStatus(data) })
          
    } catch (error) {
      console.error(`Export ${type} error:`, error)
    } finally {
      setIsExporting(prev => ({ ...prev, [type]: false }))
    }
  }

  const handleCellChange = (id: string, field: EditableCandidateField, value: EditableCandidateValue) => {
    setCandidates(prev => 
      prev.map(c => c.candidate_id === id ? { ...c, [field]: value } : c)
    )
  }

  const handleCandidateSelection = (candidateId: string) => {
    setSelectedCandidateId(candidateId)
    setCropError(false)
  }

  const selectedCandidate = candidates.find(c => c.candidate_id === selectedCandidateId)
  const metadata = metadataResult?.kind === 'available' ? metadataResult.metadata : null
  
  // Helper to extract filename from crop_path
  const getCropFilename = (path: string | null) => {
    if (!path) return null;
    const parts = path.split('/');
    return parts[parts.length - 1];
  }

  // Helper for text inputs
  const TextInput = ({ candidate, field, type = "text" }: { candidate: Candidate, field: EditableCandidateField, type?: string }) => (
    <input
      type={type}
      value={candidate[field] === null ? "" : candidate[field]}
      onChange={(e) => handleCellChange(candidate.candidate_id, field, type === "number" ? (e.target.value ? Number(e.target.value) : null) : e.target.value)}
      className="w-full bg-transparent border-b border-transparent hover:border-border focus:border-primary focus:outline-none focus:ring-0 px-1 py-1 text-sm transition-colors"
      placeholder="-"
      onClick={(e) => e.stopPropagation()}
    />
  )

  const hasOverlay = pipelineStatus?.files?.overlay_image === true;

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-[#FE0000] border-r border-[#cc0000] flex flex-col transition-all duration-300 shadow-xl z-20">
        <div className="h-16 flex items-center px-6 border-b border-white/20">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-white rounded-md flex items-center justify-center shadow-sm">
              <LayoutDashboard className="w-5 h-5 text-[#FE0000]" />
            </div>
            <h1 className="text-xl font-black tracking-tighter text-white">PLAN<span className="opacity-80 font-medium">FUGE</span></h1>
          </div>
        </div>
        
        <div className="p-4 flex-1 overflow-y-auto">
          <h2 className="text-xs uppercase font-bold text-white/70 tracking-wider mb-4">Plan Selection</h2>
          
          {loadingPlans ? (
            <div className="animate-pulse space-y-2">
              <div className="h-10 bg-border rounded-md w-full"></div>
              <div className="h-10 bg-border rounded-md w-full"></div>
            </div>
          ) : (
            <div className="space-y-4">
              <select
                value={activePlan ?? ''}
                onChange={(event) => handlePlanSelection(event.target.value)}
                disabled={plans.length === 0}
                className="w-full h-10 rounded-md border border-white/20 bg-white text-[#FE0000] px-3 text-sm font-semibold shadow-sm focus:outline-none focus:ring-2 focus:ring-white/70 disabled:opacity-60"
              >
                {plans.length === 0 ? (
                  <option value="">No plans</option>
                ) : (
                  plans.map((plan_id) => (
                    <option key={plan_id} value={plan_id}>{plan_id}</option>
                  ))
                )}
              </select>

              <form onSubmit={handleImportPlan} className="rounded-md border border-white/20 bg-white/10 p-3 space-y-3">
                <label className="block">
                  <span className="text-xs font-bold uppercase tracking-wider text-white/70">Add PDF</span>
                  <input
                    key={importInputKey}
                    type="file"
                    accept="application/pdf"
                    onChange={(event) => {
                      setSelectedImportFile(event.target.files?.[0] ?? null)
                      setImportError(null)
                      setImportMessage(null)
                    }}
                    className="mt-2 block w-full text-xs text-white file:mr-3 file:rounded-md file:border-0 file:bg-white file:px-3 file:py-2 file:text-xs file:font-semibold file:text-[#FE0000] hover:file:bg-white/90"
                  />
                </label>

                <button
                  type="submit"
                  disabled={!selectedImportFile || isImportingPlan}
                  className="w-full flex items-center justify-center gap-2 rounded-md bg-white px-3 py-2 text-sm font-bold text-[#FE0000] shadow-sm transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isImportingPlan ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  <span>{isImportingPlan ? 'Analyzing...' : 'Analyze Plan'}</span>
                </button>

                {importError && (
                  <p className="rounded-md bg-red-950/30 px-2 py-1.5 text-xs text-white">{importError}</p>
                )}
                {importMessage && (
                  <p className="rounded-md bg-white/15 px-2 py-1.5 text-xs font-medium text-white">{importMessage}</p>
                )}
              </form>

              {plans.length > 0 && (
                <nav className="space-y-1">
                  {plans.map((plan_id) => (
                    <button
                      key={plan_id}
                      onClick={() => handlePlanSelection(plan_id)}
                      className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-md font-medium transition-all duration-200 ${
                        activePlan === plan_id 
                          ? "bg-white text-[#FE0000] shadow-sm translate-x-1" 
                          : "text-white/80 hover:bg-white/10 hover:text-white"
                      }`}
                    >
                      <LayoutDashboard className={`w-4 h-4 ${activePlan === plan_id ? "text-[#FE0000]" : "text-white/60"}`} />
                      <span className="truncate">{plan_id}</span>
                    </button>
                  ))}
                </nav>
              )}
            </div>
          )}
        </div>
        
        <div className="p-4 border-t border-white/20">
          <p className="text-xs text-white/50 font-medium">Demo Mode</p>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <header className="h-16 flex items-center px-8 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-10 shrink-0">
          <h2 className="text-lg font-medium text-foreground flex items-center gap-3">
            {activePlan ? `Dashboard — ${activePlan}` : "Dashboard"}
            {metadata?.image_width_px && metadata.image_height_px && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border">
                <Maximize2 className="w-3 h-3" />
                {metadata.image_width_px} × {metadata.image_height_px} px
              </span>
            )}
            {metadata?.scale_text_visible && (
              <span className="text-xs text-muted-foreground">Scale: {metadata.scale_text_visible}</span>
            )}
            {metadata?.source_type && (
              <span className="text-xs text-muted-foreground">Source: {metadata.source_type}</span>
            )}
            {metadataResult && metadataResult.kind !== 'available' && (
              <span className={`inline-flex items-center gap-1 text-xs ${metadataResult.kind === 'error' ? 'text-red-600' : 'text-amber-600'}`}>
                <AlertCircle className="w-3 h-3" />
                {metadataResult.message}
              </span>
            )}
          </h2>
        </header>

        {/* Content Area - Split View */}
        <div className="flex-1 overflow-hidden">
          {!activePlan ? (
             <div className="h-full flex items-center justify-center p-8">
               <div className="max-w-md w-full rounded-xl border border-dashed border-border bg-muted/50 p-12 text-center text-muted-foreground">
                 <FileCheck className="w-12 h-12 mx-auto mb-4 opacity-50" />
                 <p>Please select or add a plan to view details.</p>
               </div>
             </div>
          ) : (
            <div className="h-full flex flex-col lg:flex-row divide-y lg:divide-y-0 lg:divide-x divide-border">
              
              {/* Left Column: Plan Image Viewer & Candidate Table */}
              <div className="flex-1 flex flex-col min-h-0 bg-muted/20 relative animate-in fade-in duration-500">
                
                {/* Top Half: Plan Image Viewer */}
                <div className="flex-[3] relative border-b border-border overflow-auto flex items-start justify-center p-6 bg-muted/10">
                  
                  {/* Floating Toggle Switch */}
                  {hasOverlay && (
                    <div className="absolute top-4 right-4 z-20 bg-background/90 backdrop-blur-md p-1.5 rounded-full border border-border shadow-md flex items-center space-x-1">
                      <button
                        onClick={() => setShowOverlay(false)}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                          !showOverlay 
                            ? 'bg-primary text-primary-foreground shadow-sm' 
                            : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                        }`}
                      >
                        Original
                      </button>
                      <button
                        onClick={() => setShowOverlay(true)}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors flex items-center gap-1.5 ${
                          showOverlay 
                            ? 'bg-primary text-primary-foreground shadow-sm' 
                            : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                        }`}
                      >
                        <Layers className="w-3 h-3" />
                        Overlay
                      </button>
                    </div>
                  )}

                  {imageError ? (
                    <div className="m-auto max-w-sm w-full rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center text-red-600 dark:text-red-400">
                      <AlertCircle className="w-10 h-10 mx-auto mb-3 opacity-80" />
                      <h3 className="font-semibold mb-1">Image Missing</h3>
                      <p className="text-sm opacity-80">
                        Could not load {showOverlay ? 'overlay' : 'original'} image for {activePlan}
                      </p>
                    </div>
                  ) : (
                    <div className="relative rounded-lg overflow-hidden border border-border shadow-md bg-white max-w-full">
                      <img 
                        src={showOverlay ? `/api/images/overlays/${activePlan}` : `/api/images/pages/${activePlan}`} 
                        alt={`Plan ${activePlan} ${showOverlay ? 'Overlay' : ''}`}
                        className="max-w-full h-auto object-contain block"
                        onError={() => setImageError(true)}
                      />
                    </div>
                  )}
                </div>

                {/* Bottom Half: Editable Candidate Table */}
                <div className="flex-[2] bg-background flex flex-col min-h-0">
                  <div className="px-4 py-3 border-b border-border flex items-center justify-between bg-card">
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold text-sm">Detected Candidates ({candidates.length})</h3>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${candidateSourceBadgeClass(candidateSource)}`}>
                        {candidateSourceLabel(candidateSource)}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      {candidateSource === 'sample' ? (
                        <button onClick={exitSampleMode} className="text-xs font-medium text-primary hover:underline">Return to real candidates</button>
                      ) : (
                        <button onClick={loadSampleCandidates} className="text-xs font-medium text-primary hover:underline">Use sample candidates</button>
                      )}
                      <p className="text-xs text-muted-foreground">Click a row to view crop preview.</p>
                    </div>
                  </div>
                  
                  <div className="flex-1 overflow-auto p-0">
                    {loadingCandidates ? (
                      <div className="flex items-center justify-center h-full text-muted-foreground">
                        <Loader2 className="w-6 h-6 animate-spin mr-2" />
                        Loading candidates...
                      </div>
                    ) : candidates.length === 0 ? (
                      <div className="flex items-center justify-center h-full text-muted-foreground p-4 text-sm text-center">
                        No candidates found for this plan.
                      </div>
                    ) : (
                      <div className="inline-block min-w-full align-middle">
                        <table className="min-w-full divide-y divide-border border-b border-border">
                          <thead className="bg-muted/50 sticky top-0 z-10 backdrop-blur-sm">
                            <tr>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">ID</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">Status</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">Raw Text</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">Label Type</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">W (mm)</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">H (mm)</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">Ø (mm)</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">RA</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">OK</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">Reference</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">Comment</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border bg-card">
                            {candidates.map((c) => (
                              <tr 
                                key={c.candidate_id} 
                                onClick={() => handleCandidateSelection(c.candidate_id)}
                                className={`transition-colors cursor-pointer ${selectedCandidateId === c.candidate_id ? 'bg-primary/10 hover:bg-primary/20' : 'hover:bg-muted/30'}`}
                              >
                                <td className="px-4 py-2 whitespace-nowrap text-xs font-medium text-muted-foreground border-r border-border/50 bg-muted/5">
                                  {c.candidate_id}
                                </td>
                                <td className="px-2 py-2 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                                  <select 
                                    value={c.status || 'needs_review'} 
                                    onChange={(e) => handleCellChange(c.candidate_id, 'status', e.target.value)}
                                    className={`text-xs px-2 py-1 rounded border-none font-medium focus:ring-1 focus:ring-primary ${
                                      c.status === 'verified' ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' :
                                      c.status === 'rejected' ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400' :
                                      c.status === 'duplicate_candidate' ? 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400' :
                                      'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                                    }`}
                                  >
                                    <option value="needs_review">Needs Review</option>
                                    <option value="verified">Verified</option>
                                    <option value="rejected">Rejected</option>
                                    <option value="duplicate_candidate">Duplicate</option>
                                  </select>
                                </td>
                                <td className="px-2 py-2 min-w-[120px]"><TextInput candidate={c} field="raw_text" /></td>
                                <td className="px-2 py-2 min-w-[100px]"><TextInput candidate={c} field="label_type" /></td>
                                <td className="px-2 py-2 min-w-[80px]"><TextInput candidate={c} field="width_mm" type="number" /></td>
                                <td className="px-2 py-2 min-w-[80px]"><TextInput candidate={c} field="height_mm" type="number" /></td>
                                <td className="px-2 py-2 min-w-[80px]"><TextInput candidate={c} field="diameter_mm" type="number" /></td>
                                <td className="px-2 py-2 min-w-[80px]"><TextInput candidate={c} field="ra_value" /></td>
                                <td className="px-2 py-2 min-w-[80px]"><TextInput candidate={c} field="ok_value" /></td>
                                <td className="px-2 py-2 min-w-[120px]"><TextInput candidate={c} field="reference" /></td>
                                <td className={`px-2 py-2 min-w-[150px] ${c.label_type && !hasCandidateDimensions(c) ? 'bg-yellow-50 dark:bg-yellow-900/10' : ''}`}>
                                  <TextInput candidate={c} field="review_comment" />
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>

              </div>

              {/* Right Column: Status & Actions (Fixed width on desktop) */}
              <div className="w-full lg:w-96 shrink-0 overflow-y-auto p-6 bg-background space-y-6">
                
                {/* Crop Preview Panel */}
                <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
                  <h4 className="text-base font-semibold mb-4 flex items-center gap-2">
                    <ImageIcon className="w-4 h-4 text-primary" />
                    Crop Preview
                  </h4>
                  {!selectedCandidate ? (
                    <div className="h-32 border border-dashed border-border rounded-lg flex items-center justify-center bg-muted/30">
                      <p className="text-sm text-muted-foreground">Select a candidate from the table.</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* Crop Image View */}
                      {!selectedCandidate.crop_path ? (
                        <div className="h-32 border border-dashed border-border rounded-lg flex flex-col items-center justify-center bg-muted/30">
                          <ImageIcon className="w-6 h-6 text-muted-foreground/50 mb-2" />
                          <p className="text-sm text-muted-foreground">No crop image available</p>
                        </div>
                      ) : cropError ? (
                        <div className="h-32 border border-dashed border-red-500/30 rounded-lg flex flex-col items-center justify-center bg-red-500/5">
                          <AlertCircle className="w-6 h-6 text-red-400 mb-2" />
                          <p className="text-xs text-red-500 text-center px-4">Failed to load crop image</p>
                        </div>
                      ) : (
                        <div className="border border-border rounded-lg overflow-hidden bg-white flex items-center justify-center min-h-[128px] p-2">
                          <img 
                            src={`/api/images/crops/${getCropFilename(selectedCandidate.crop_path)}`}
                            alt="Crop Preview"
                            className="max-w-full max-h-48 object-contain"
                            onError={() => setCropError(true)}
                          />
                        </div>
                      )}
                      
                      {/* Parsed Data Details */}
                      <div className="bg-muted/30 rounded-lg p-3 space-y-2 border border-border">
                        <div className="flex justify-between items-center border-b border-border/50 pb-2 mb-2">
                          <span className="text-xs font-semibold text-muted-foreground">ID</span>
                          <span className="text-xs font-mono text-foreground truncate max-w-[150px]" title={selectedCandidate.candidate_id}>
                            {selectedCandidate.candidate_id}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="block text-muted-foreground mb-0.5">Label Type</span>
                            <span className="font-medium">{selectedCandidate.label_type || '-'}</span>
                          </div>
                          <div>
                            <span className="block text-muted-foreground mb-0.5">Raw Text</span>
                            <span className="font-medium">{selectedCandidate.raw_text || '-'}</span>
                          </div>
                          <div>
                            <span className="block text-muted-foreground mb-0.5">Dimensions (mm)</span>
                            <span className="font-medium">
                              {formatCandidateDimensions(selectedCandidate)}
                            </span>
                          </div>
                          <div>
                            <span className="block text-muted-foreground mb-0.5">Reference</span>
                            <span className="font-medium">{selectedCandidate.reference || '-'}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Status Panel */}
                <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
                  <h4 className="text-base font-semibold mb-4 flex items-center gap-2">
                    <FileCheck className="w-4 h-4 text-green-500" />
                    Pipeline Status
                  </h4>
                  <ul className="space-y-3">
                    <li className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2 text-foreground">
                        <div className={`w-2 h-2 rounded-full ${pipelineStatus?.files?.page_image ? 'bg-green-500' : 'bg-red-500'}`} />
                        Source Image
                      </span>
                      <span className="text-muted-foreground text-xs">{pipelineStatus?.files?.page_image ? 'Available' : 'Missing'}</span>
                    </li>
                    <li className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2 text-foreground">
                        <div className={`w-2 h-2 rounded-full ${pipelineStatus?.files?.overlay_image ? 'bg-green-500' : 'bg-yellow-500'}`} />
                        CV Overlay
                      </span>
                      <span className="text-muted-foreground text-xs">{pipelineStatus?.files?.overlay_image ? 'Available' : 'Missing'}</span>
                    </li>
                    <li className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2 text-foreground">
                        <div className={`w-2 h-2 rounded-full ${pipelineStatus?.files?.candidates_json ? 'bg-green-500' : 'bg-yellow-500'}`} />
                        Candidates JSON
                      </span>
                      <span className="text-muted-foreground text-xs">{pipelineStatus?.files?.candidates_json ? 'Loaded' : 'Missing'}</span>
                    </li>
                    <li className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2 text-foreground">
                        <div className={`w-2 h-2 rounded-full ${pipelineStatus?.files?.review_json ? 'bg-green-500' : 'bg-yellow-500'}`} />
                        Review Draft
                      </span>
                      <span className="text-muted-foreground text-xs">{pipelineStatus?.files?.review_json ? 'Saved' : 'Missing'}</span>
                    </li>
                    <li className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2 text-foreground">
                        <div className={`w-2 h-2 rounded-full ${pipelineStatus?.files?.export_json ? 'bg-green-500' : 'bg-yellow-500'}`} />
                        Verified Export
                      </span>
                      <span className="text-muted-foreground text-xs">{pipelineStatus?.files?.export_json ? 'Exported' : 'Missing'}</span>
                    </li>
                  </ul>
                </div>

                {/* Quick Actions */}
                <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
                  <h4 className="text-base font-semibold mb-4">Quick Actions</h4>
                  <div className="grid grid-cols-2 gap-3">
                    <button 
                      onClick={handleSave}
                      disabled={isSaving || candidates.length === 0 || !canSaveCandidates(candidateSource)}
                      className="col-span-2 flex items-center justify-center gap-2 p-3 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm font-medium"
                    >
                      {isSaving ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : saveSuccess ? (
                        <CheckCircle2 className="w-4 h-4 text-green-400" />
                      ) : (
                        <Save className="w-4 h-4" />
                      )}
                      <span>{candidateSource === 'sample' ? 'Sample data is not saved' : isSaving ? 'Saving...' : saveSuccess ? 'Saved!' : 'Review Detections'}</span>
                    </button>
                    <button 
                      onClick={() => handleExport('csv')}
                      disabled={isExporting.csv || candidates.length === 0}
                      className="flex flex-col items-center justify-center p-3 rounded-lg border border-border bg-muted/30 hover:bg-primary/5 hover:border-primary/20 transition-all group disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isExporting.csv ? (
                        <Loader2 className="w-5 h-5 mb-1 animate-spin text-primary" />
                      ) : (
                        <Download className="w-5 h-5 mb-1 text-muted-foreground group-hover:text-primary transition-colors" />
                      )}
                      <span className="text-xs font-medium text-foreground">{isExporting.csv ? 'Exporting...' : 'Export CSV'}</span>
                    </button>
                    <button 
                      onClick={() => handleExport('json')}
                      disabled={isExporting.json || candidates.length === 0}
                      className="flex flex-col items-center justify-center p-3 rounded-lg border border-border bg-muted/30 hover:bg-primary/5 hover:border-primary/20 transition-all group disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isExporting.json ? (
                        <Loader2 className="w-5 h-5 mb-1 animate-spin text-primary" />
                      ) : (
                        <FileJson className="w-5 h-5 mb-1 text-muted-foreground group-hover:text-primary transition-colors" />
                      )}
                      <span className="text-xs font-medium text-foreground">{isExporting.json ? 'Exporting...' : 'Export JSON'}</span>
                    </button>
                  </div>
                </div>

              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App

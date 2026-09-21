import { useState, useEffect, useCallback, Component } from 'react'
import './App.css'
import { 
  Play, Pause, RefreshCw, Activity, Zap, AlertTriangle, 
  CheckCircle, Server, Wifi, WifiOff, Gauge, BarChart3,
  TrendingUp, TrendingDown, Minus, ArrowRight
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'

// Types
interface SessionStatus {
  session: {
    session_id: string
    current_mode: string
    request_count: number
    success_count: number
    failure_count: number
    accumulated_count: number
    current_stability_score: number
    transition_history: Array<{
      from: string
      to: string
      stability_score: number
      timestamp: number
    }>
  }
  network_features: {
    avg_latency: number
    std_latency: number
    failure_rate: number
    timeout_rate: number
    avg_retries: number
    request_velocity: number
    jitter: number
    total_requests: number
  }
  prediction: {
    stability_score: number
    explanations: string[]
    feature_vector: Record<string, number>
  }
}

interface ApiResponse {
  status_code: number
  body: {
    status?: string
    mode?: string
    _meta?: {
      mode: string
      stability_score: number
      session_id: string
      processing_time_ms: number
    }
    [key: string]: any
  }
}

// FIX #13: Read API base from environment variable with localhost fallback
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

// ─── FIX #11: Error Boundary ─────────────────────────────────────────────────
interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class ErrorBoundary extends Component<{ children: React.ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-900 flex items-center justify-center p-6">
          <div className="bg-red-900/40 border border-red-500 rounded-lg p-8 max-w-md w-full text-center space-y-4">
            <AlertTriangle className="w-12 h-12 text-red-400 mx-auto" />
            <h2 className="text-xl font-bold text-white">Something went wrong</h2>
            <p className="text-slate-400 text-sm">
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-sm"
            >
              Reload Page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
// ─────────────────────────────────────────────────────────────────────────────

function App() {
  const [sessionId, setSessionId] = useState<string>('')
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [lastResponse, setLastResponse] = useState<ApiResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Generate session ID on mount
  useEffect(() => {
    setSessionId(`demo_${Date.now()}`)
  }, [])

  // FIX #12: Fetch session status as soon as session ID is set
  useEffect(() => {
    if (!sessionId) return
    fetchSessionStatus()
  }, [sessionId])

  // Auto refresh session status
  useEffect(() => {
    if (!autoRefresh || !sessionId) return
    
    const interval = setInterval(() => {
      fetchSessionStatus()
    }, 2000)
    
    return () => clearInterval(interval)
  }, [autoRefresh, sessionId])

  const fetchSessionStatus = async () => {
    if (!sessionId) return
    
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}`)
      if (response.ok) {
        const data = await response.json()
        setSessionStatus(data)
        setError(null)
      }
    } catch (err) {
      setError('Failed to fetch session status. Is the backend running?')
    }
  }

  const simulateNetwork = async (condition: string) => {
    if (!sessionId) return
    
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ condition })
      })
      
      if (response.ok) {
        const data = await response.json()
        setSessionStatus(data.session_status)
        setError(null)
      }
    } catch (err) {
      setError('Failed to simulate network condition')
    }
    setLoading(false)
  }

  const submitRequest = async (mode: 'normal' | 'degraded' | 'critical') => {
    if (!sessionId) return
    
    setLoading(true)
    
    const testAnswers = Array.from({ length: 5 }, (_, i) => ({
      question_id: i + 1,
      answer: String.fromCharCode(65 + (i % 4)),
      time_spent: 30 + i * 5
    }))
    
    const latencyMap = {
      normal: 50,
      degraded: 500,
      critical: 2000
    }
    
    try {
      let response
      
      if (mode === 'normal') {
        response = await fetch(`${API_BASE}/exam/submit`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'X-Session-Id': sessionId,
            'X-Simulated-Latency': String(latencyMap[mode])
          },
          body: JSON.stringify({
            student_id: 'demo_student',
            exam_id: 'demo_exam',
            answers: testAnswers,
            simulated_latency: latencyMap[mode]
          })
        })
      } else if (mode === 'degraded') {
        response = await fetch(`${API_BASE}/exam/batch`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'X-Session-Id': sessionId,
            'X-Simulated-Latency': String(latencyMap[mode])
          },
          body: JSON.stringify({
            student_id: 'demo_student',
            exam_id: 'demo_exam',
            answers: testAnswers,
            batch_size: 5,
            finalize: true,
            simulated_latency: latencyMap[mode]
          })
        })
      } else {
        response = await fetch(`${API_BASE}/exam/accumulate`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'X-Session-Id': sessionId,
            'X-Simulated-Latency': String(latencyMap[mode])
          },
          body: JSON.stringify({
            student_id: 'demo_student',
            exam_id: 'demo_exam',
            answers: testAnswers,
            simulated_latency: latencyMap[mode]
          })
        })
      }
      
      if (response.ok) {
        const data = await response.json()
        setLastResponse(data)
        await fetchSessionStatus()
        setError(null)
      }
    } catch (err) {
      setError('Failed to submit request. Is the backend running on port 8000?')
    }
    
    setLoading(false)
  }

  const resetSession = () => {
    setSessionId(`demo_${Date.now()}`)
    setSessionStatus(null)
    setLastResponse(null)
    setError(null)
  }

  const getModeColor = (mode: string) => {
    switch (mode) {
      case 'normal': return 'bg-green-500'
      case 'degraded': return 'bg-yellow-500'
      case 'critical': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const getModeBadgeVariant = (mode: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
    switch (mode) {
      case 'normal': return 'default'
      case 'degraded': return 'secondary'
      case 'critical': return 'destructive'
      default: return 'outline'
    }
  }

  const getStabilityColor = (score: number) => {
    if (score >= 0.8) return 'text-green-500'
    if (score >= 0.5) return 'text-yellow-500'
    return 'text-red-500'
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              Adaptive Middleware Prototype
            </h1>
            <p className="text-slate-400 mt-1">
              Session-aware cloud middleware with dynamic execution mode adaptation
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={autoRefresh ? 'bg-green-600/20 border-green-500' : ''}
            >
              {autoRefresh ? <Pause className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
              {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
            </Button>
            <Button variant="outline" size="sm" onClick={resetSession}>
              <RefreshCw className="w-4 h-4 mr-2" />
              New Session
            </Button>
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="bg-red-900/50 border-red-500">
            <AlertTriangle className="w-4 h-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Session Info Bar */}
        <Card className="bg-slate-800/50 border-slate-700">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div>
                  <span className="text-slate-400 text-sm">Session ID</span>
                  <p className="font-mono text-sm">{sessionId}</p>
                </div>
                <Separator orientation="vertical" className="h-8 bg-slate-600" />
                <div>
                  <span className="text-slate-400 text-sm">Current Mode</span>
                  <div className="flex items-center gap-2">
                    {sessionStatus?.session?.current_mode && (
                      <>
                        <div className={`w-3 h-3 rounded-full ${getModeColor(sessionStatus.session.current_mode)} animate-pulse`} />
                        <Badge variant={getModeBadgeVariant(sessionStatus.session.current_mode)} className="capitalize">
                          {sessionStatus.session.current_mode}
                        </Badge>
                      </>
                    )}
                  </div>
                </div>
                <Separator orientation="vertical" className="h-8 bg-slate-600" />
                <div>
                  <span className="text-slate-400 text-sm">Stability Score</span>
                  <p className={`text-lg font-bold ${getStabilityColor(sessionStatus?.prediction?.stability_score || 1)}`}>
                    {((sessionStatus?.prediction?.stability_score || 0) * 100).toFixed(1)}%
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <span className="text-slate-400 text-sm">Requests</span>
                  <p className="text-xl font-bold">{sessionStatus?.session?.request_count || 0}</p>
                </div>
                <div className="text-right">
                  <span className="text-slate-400 text-sm">Success</span>
                  <p className="text-xl font-bold text-green-400">{sessionStatus?.session?.success_count || 0}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Controls */}
          <div className="space-y-6">
            {/* Network Simulation */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Wifi className="w-5 h-5 text-blue-400" />
                  Network Simulation
                </CardTitle>
                <CardDescription>Simulate different network conditions</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button 
                  variant="outline" 
                  className="w-full justify-start border-green-500/50 hover:bg-green-500/20"
                  onClick={() => simulateNetwork('good')}
                  disabled={loading}
                >
                  <Wifi className="w-4 h-4 mr-2 text-green-400" />
                  Good Network (50ms)
                </Button>
                <Button 
                  variant="outline" 
                  className="w-full justify-start border-yellow-500/50 hover:bg-yellow-500/20"
                  onClick={() => simulateNetwork('poor')}
                  disabled={loading}
                >
                  <Wifi className="w-4 h-4 mr-2 text-yellow-400" />
                  Poor Network (800ms)
                </Button>
                <Button 
                  variant="outline" 
                  className="w-full justify-start border-orange-500/50 hover:bg-orange-500/20"
                  onClick={() => simulateNetwork('bad')}
                  disabled={loading}
                >
                  <WifiOff className="w-4 h-4 mr-2 text-orange-400" />
                  Bad Network (2000ms)
                </Button>
                <Button 
                  variant="outline" 
                  className="w-full justify-start border-red-500/50 hover:bg-red-500/20"
                  onClick={() => simulateNetwork('terrible')}
                  disabled={loading}
                >
                  <WifiOff className="w-4 h-4 mr-2 text-red-400" />
                  Terrible Network (5000ms)
                </Button>
              </CardContent>
            </Card>

            {/* Mode Testing */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-purple-400" />
                  Test Modes
                </CardTitle>
                <CardDescription>Submit test requests in different modes</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button 
                  className="w-full bg-green-600 hover:bg-green-700"
                  onClick={() => submitRequest('normal')}
                  disabled={loading}
                >
                  <Zap className="w-4 h-4 mr-2" />
                  Test Normal Mode
                </Button>
                <Button 
                  className="w-full bg-yellow-600 hover:bg-yellow-700"
                  onClick={() => submitRequest('degraded')}
                  disabled={loading}
                >
                  <Gauge className="w-4 h-4 mr-2" />
                  Test Degraded Mode
                </Button>
                <Button 
                  className="w-full bg-red-600 hover:bg-red-700"
                  onClick={() => submitRequest('critical')}
                  disabled={loading}
                >
                  <AlertTriangle className="w-4 h-4 mr-2" />
                  Test Critical Mode
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Middle Column - Metrics */}
          <div className="space-y-6">
            <Card className="bg-slate-800/50 border-slate-700 h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-cyan-400" />
                  Network Metrics
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {sessionStatus?.network_features ? (
                  <>
                    <MetricRow 
                      label="Average Latency" 
                      value={`${sessionStatus.network_features.avg_latency.toFixed(1)} ms`}
                      icon={<Activity className="w-4 h-4" />}
                      trend={sessionStatus.network_features.avg_latency > 500 ? 'up' : 'down'}
                    />
                    <MetricRow 
                      label="Std Deviation" 
                      value={`${sessionStatus.network_features.std_latency.toFixed(1)} ms`}
                      icon={<TrendingUp className="w-4 h-4" />}
                    />
                    <MetricRow 
                      label="Failure Rate" 
                      value={`${(sessionStatus.network_features.failure_rate * 100).toFixed(1)}%`}
                      icon={<AlertTriangle className="w-4 h-4" />}
                      alert={sessionStatus.network_features.failure_rate > 0.1}
                    />
                    <MetricRow 
                      label="Timeout Rate" 
                      value={`${(sessionStatus.network_features.timeout_rate * 100).toFixed(1)}%`}
                      icon={<WifiOff className="w-4 h-4" />}
                      alert={sessionStatus.network_features.timeout_rate > 0.05}
                    />
                    <MetricRow 
                      label="Avg Retries" 
                      value={sessionStatus.network_features.avg_retries.toFixed(2)}
                      icon={<RefreshCw className="w-4 h-4" />}
                    />
                    <MetricRow 
                      label="Request Velocity" 
                      value={`${sessionStatus.network_features.request_velocity.toFixed(2)} req/s`}
                      icon={<Gauge className="w-4 h-4" />}
                    />
                    <MetricRow 
                      label="Jitter" 
                      value={`${sessionStatus.network_features.jitter.toFixed(1)} ms`}
                      icon={<Activity className="w-4 h-4" />}
                    />
                  </>
                ) : (
                  <div className="text-center text-slate-500 py-8">
                    <Server className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>No metrics available yet</p>
                    <p className="text-sm">Submit a request or simulate network conditions</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right Column - Status & Transitions */}
          <div className="space-y-6">
            <Tabs defaultValue="transitions" className="w-full">
              <TabsList className="grid w-full grid-cols-2 bg-slate-800">
                <TabsTrigger value="transitions">Transitions</TabsTrigger>
                <TabsTrigger value="prediction">Prediction</TabsTrigger>
              </TabsList>
              
              <TabsContent value="transitions" className="mt-4">
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <ArrowRight className="w-4 h-4 text-blue-400" />
                      Mode Transition History
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {sessionStatus?.session?.transition_history?.length > 0 ? (
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {sessionStatus.session.transition_history.map((transition, idx) => (
                          <div key={idx} className="flex items-center gap-2 p-2 bg-slate-700/50 rounded text-sm">
                            <Badge variant="outline" className="capitalize text-xs">
                              {transition.from}
                            </Badge>
                            <ArrowRight className="w-3 h-3 text-slate-400" />
                            <Badge variant={getModeBadgeVariant(transition.to)} className="capitalize text-xs">
                              {transition.to}
                            </Badge>
                            <span className="text-xs text-slate-400 ml-auto">
                              {(transition.stability_score * 100).toFixed(0)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-500 text-sm text-center py-4">
                        No transitions yet
                      </p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
              
              <TabsContent value="prediction" className="mt-4">
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <TrendingUp className="w-4 h-4 text-green-400" />
                      Prediction Explanation
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {sessionStatus?.prediction?.explanations ? (
                      <div className="space-y-3">
                        <div className="text-center">
                          <div className="text-3xl font-bold text-white">
                            {(sessionStatus.prediction.stability_score * 100).toFixed(1)}%
                          </div>
                          <p className="text-slate-400 text-sm">Stability Score</p>
                        </div>
                        <Progress 
                          value={sessionStatus.prediction.stability_score * 100} 
                          className="h-2"
                        />
                        <div className="space-y-1 mt-4">
                          {sessionStatus.prediction.explanations.map((exp, idx) => (
                            <div key={idx} className="flex items-start gap-2 text-sm">
                              <Activity className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                              <span className="text-slate-300">{exp}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <p className="text-slate-500 text-sm text-center py-4">
                        No prediction data available
                      </p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            {/* Last Response */}
            {lastResponse && (
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <CheckCircle className="w-4 h-4 text-green-400" />
                    Last Response
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Status</span>
                      <Badge variant={lastResponse.status_code === 200 ? 'default' : 'secondary'}>
                        {lastResponse.status_code}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Mode</span>
                      <Badge variant="outline" className="capitalize">
                        {lastResponse.body._meta?.mode}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Processing Time</span>
                      <span>{lastResponse.body._meta?.processing_time_ms} ms</span>
                    </div>
                    <div className="mt-3 p-2 bg-slate-900 rounded">
                      <pre className="text-xs text-slate-400 overflow-x-auto">
                        {JSON.stringify(lastResponse.body, null, 2)}
                      </pre>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        {/* Mode Comparison */}
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="w-5 h-5 text-indigo-400" />
              Execution Mode Comparison
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <ModeCard 
                mode="Normal"
                color="green"
                description="Granular, step-by-step processing with real-time validation"
                characteristics={[
                  "10+ network trips (one per question)",
                  "Immediate confirmations",
                  "Rich error messages",
                  "Best for good network conditions"
                ]}
              />
              <ModeCard 
                mode="Degraded"
                color="yellow"
                description="Batch processing with compression and fewer confirmations"
                characteristics={[
                  "2-3 network trips (batched)",
                  "Server-side validation",
                  "Compressed responses",
                  "Best for moderate network issues"
                ]}
              />
              <ModeCard 
                mode="Critical"
                color="red"
                description="Minimal communication with async server-side processing"
                characteristics={[
                  "1-2 network trips (single transmission)",
                  "Minimal payload",
                  "Async processing",
                  "Best for severe network degradation"
                ]}
              />
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <div className="text-center text-slate-500 text-sm py-4">
          <p>Adaptive Middleware Prototype • Patent Demo</p>
          <p className="mt-1">Backend: <code className="bg-slate-800 px-2 py-0.5 rounded">{API_BASE}</code></p>
        </div>
      </div>
    </div>
  )
}

// Helper Components

function MetricRow({ 
  label, 
  value, 
  icon, 
  trend,
  alert 
}: { 
  label: string
  value: string
  icon: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
  alert?: boolean
}) {
  return (
    <div className={`flex items-center justify-between p-3 rounded-lg ${alert ? 'bg-red-500/10 border border-red-500/30' : 'bg-slate-700/30'}`}>
      <div className="flex items-center gap-3">
        <div className={`${alert ? 'text-red-400' : 'text-slate-400'}`}>
          {icon}
        </div>
        <span className="text-slate-300">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className={`font-mono font-semibold ${alert ? 'text-red-400' : 'text-white'}`}>
          {value}
        </span>
        {trend === 'up' && <TrendingUp className="w-4 h-4 text-red-400" />}
        {trend === 'down' && <TrendingDown className="w-4 h-4 text-green-400" />}
        {trend === 'neutral' && <Minus className="w-4 h-4 text-slate-400" />}
      </div>
    </div>
  )
}

function ModeCard({ 
  mode, 
  color, 
  description, 
  characteristics 
}: { 
  mode: string
  color: 'green' | 'yellow' | 'red'
  description: string
  characteristics: string[]
}) {
  const colorClasses = {
    green: 'border-green-500/30 bg-green-500/5',
    yellow: 'border-yellow-500/30 bg-yellow-500/5',
    red: 'border-red-500/30 bg-red-500/5'
  }

  const titleColors = {
    green: 'text-green-400',
    yellow: 'text-yellow-400',
    red: 'text-red-400'
  }

  return (
    <div className={`p-4 rounded-lg border ${colorClasses[color]}`}>
      <h3 className={`text-lg font-bold ${titleColors[color]} mb-2`}>{mode} Mode</h3>
      <p className="text-slate-400 text-sm mb-3">{description}</p>
      <ul className="space-y-1">
        {characteristics.map((char, idx) => (
          <li key={idx} className="flex items-start gap-2 text-sm text-slate-300">
            <CheckCircle className={`w-4 h-4 mt-0.5 flex-shrink-0 ${titleColors[color]}`} />
            {char}
          </li>
        ))}
      </ul>
    </div>
  )
}

// FIX #11: Wrap export in ErrorBoundary so any component crash shows a
// friendly message instead of a blank white screen
export default function AppWithErrorBoundary() {
  return (
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  )
}
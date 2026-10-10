import { useEffect, useState } from 'react'

import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { ExperimentDetails } from './pages/ExperimentDetails'
import { Experiments } from './pages/Experiments'
import { Infrastructure } from './pages/Infrastructure'
import { Results } from './pages/Results'
import './App.css'

function getExperimentId(hash: string): string | null {
  const experimentPrefix = '#experiment/'
  if (!hash.startsWith(experimentPrefix)) return null

  try {
    return decodeURIComponent(hash.slice(experimentPrefix.length))
  } catch {
    return null
  }
}

function App() {
  const [hash, setHash] = useState(() => window.location.hash)

  useEffect(() => {
    const handleHashChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  const experimentId = getExperimentId(hash)

  const page = experimentId
    ? <ExperimentDetails key={experimentId} experimentId={experimentId} />
    : hash === '#experiments'
      ? <Experiments />
      : hash === '#infrastructure'
        ? <Infrastructure />
        : hash === '#results'
          ? <Results />
          : <Dashboard />

  return (
    <Layout currentHash={hash}>
      {page}
    </Layout>
  )
}

export default App
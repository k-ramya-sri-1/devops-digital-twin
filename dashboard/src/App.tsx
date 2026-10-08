import { useEffect, useState } from 'react'

import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { ExperimentDetails } from './pages/ExperimentDetails'
import './App.css'

function App() {
  const [hash, setHash] = useState(() => window.location.hash)

  useEffect(() => {
    const handleHashChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  const experimentPrefix = '#experiment/'
  const experimentId = hash.startsWith(experimentPrefix)
    ? decodeURIComponent(hash.slice(experimentPrefix.length))
    : null

  return (
    <Layout>
      {experimentId ? <ExperimentDetails key={experimentId} experimentId={experimentId} /> : <Dashboard />}
    </Layout>
  )
}

export default App
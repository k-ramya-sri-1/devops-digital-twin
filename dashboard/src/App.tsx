import { useEffect, useState } from 'react'

import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { ExperimentDetails } from './pages/ExperimentDetails'
import { Experiments } from './pages/Experiments'
import { PlaceholderPage } from './pages/PlaceholderPage'
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

  const page = experimentId
    ? <ExperimentDetails key={experimentId} experimentId={experimentId} />
    : hash === '#experiments'
      ? <Experiments />
      : hash === '#infrastructure'
        ? <PlaceholderPage title="Infrastructure" />
        : hash === '#results'
          ? <PlaceholderPage title="Results" />
          : <Dashboard />

  return (
    <Layout currentHash={hash}>
      {page}
    </Layout>
  )
}

export default App
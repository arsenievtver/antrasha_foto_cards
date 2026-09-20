import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { assertAppIdentity } from './utils/assertAppIdentity.js'
import { bindAppVh } from './utils/appVh.js'
import './index.css'
import App from './App.jsx'

if (assertAppIdentity('client')) {
  bindAppVh()
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

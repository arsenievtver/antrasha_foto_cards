import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { bindAppVh } from './utils/appVh.js'
import './index.css'
import App from './App.jsx'

bindAppVh()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

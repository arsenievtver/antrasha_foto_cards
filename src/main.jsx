import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import { assertAppIdentity } from './utils/assertAppIdentity.js'
import { bindAppVh } from './utils/appVh.js'
import { preparePushServiceWorker } from './push/notifications.js'
import './index.css'
import App from './App.jsx'

if (assertAppIdentity('client')) {
  registerSW({
    immediate: true,
    onRegisterError(error) {
      console.error('[pwa] service worker registration failed', error)
    },
  })
  void preparePushServiceWorker()
  bindAppVh()
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

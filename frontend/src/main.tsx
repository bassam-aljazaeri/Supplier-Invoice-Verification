import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { SessionContext } from './authContext.tsx'
import { session, startBrowserSession } from './authRuntime.ts'
import { configureDocumentDownloads } from './documentDownloads.ts'

configureDocumentDownloads(import.meta.env.VITE_DOCUMENT_S3_ORIGIN)
startBrowserSession()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SessionContext value={session}><App /></SessionContext>
  </StrictMode>,
)

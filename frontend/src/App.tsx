import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import './App.css'
import AppRoutes from './routes/AppRoutes'

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
      <Toaster
        position="bottom-right"
        theme="dark"
        toastOptions={{
          style: {
            background: 'var(--bg-surface)',
            border: '3px solid var(--bg-surface-light)',
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-body)',
          },
        }}
      />
    </BrowserRouter>
  )
}

import { Boxes } from 'lucide-react'
import { SessionsPage } from './pages/SessionsPage'

function App() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <div className="mr-4 flex">
            <div className="mr-6 flex items-center space-x-2">
              <Boxes className="h-6 w-6 text-primary" />
              <span className="font-bold">TaskWeaver Sessions</span>
            </div>
          </div>
        </div>
      </header>
      <main className="container py-6">
        <SessionsPage />
      </main>
    </div>
  )
}

export default App

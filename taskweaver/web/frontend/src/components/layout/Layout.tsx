import { Outlet, NavLink } from 'react-router-dom'
import { Boxes, MessageSquare } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Layout() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <div className="mr-4 flex">
            <NavLink to="/" className="mr-6 flex items-center space-x-2">
              <Boxes className="h-6 w-6 text-primary" />
              <span className="font-bold">TaskWeaver</span>
            </NavLink>
          </div>
          <nav className="flex items-center space-x-6 text-sm font-medium">
            <NavLink
              to="/chat"
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 transition-colors hover:text-foreground/80',
                  isActive ? 'text-foreground' : 'text-foreground/60'
                )
              }
            >
              <MessageSquare className="h-4 w-4" />
              Chat
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="container py-6">
        <Outlet />
      </main>
    </div>
  )
}

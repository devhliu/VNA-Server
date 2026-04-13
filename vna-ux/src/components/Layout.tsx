import { useState, useEffect } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { Menu, X, Home, Database, Tag, Activity, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'

const navigation = [
  { name: 'Dashboard', path: '/', icon: Home },
  { name: 'Archive', path: '/archive', icon: Database },
  { name: 'Labels', path: '/labels', icon: Tag },
  { name: 'System', path: '/system', icon: Activity },
  { name: 'Logs', path: '/logs', icon: FileText },
]

const pageTitleMap: Record<string, string> = {
  '/': 'Dashboard',
  '/archive': 'Archive Browser',
  '/labels': 'Labels',
  '/system': 'System Status',
  '/logs': 'System Logs',
}

function NavLinks({ location, sidebarOpen, onItemClick }: { location: ReturnType<typeof useLocation>; sidebarOpen: boolean; onItemClick: () => void }) {
  return (
    <>
      {navigation.map((item) => {
        const isActive = location.pathname === item.path
        return (
          <Link
            key={item.name}
            to={item.path}
            onClick={onItemClick}
            className={cn(
              "flex items-center px-4 py-3 rounded-xl group transition-all duration-200",
              isActive
                ? "bg-blue-50 text-blue-700 shadow-sm"
                : "text-gray-700 hover:bg-gray-100"
            )}
          >
            <div className={cn(
              "flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-200",
              isActive
                ? "bg-blue-100"
                : "bg-transparent group-hover:bg-gray-200"
            )}>
              <item.icon size={18} className={cn(
                isActive ? "text-blue-600" : "text-gray-500 group-hover:text-gray-700"
              )} />
            </div>
            {sidebarOpen && <span className="ml-3 text-sm font-medium">{item.name}</span>}
          </Link>
        )
      })}
    </>
  )
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const location = useLocation()
  const currentPage = pageTitleMap[location.pathname] || 'VNA Server'

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768) {
        setSidebarOpen(false)
        setMobileSidebarOpen(false)
      } else {
        setSidebarOpen(true)
      }
    }
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    setMobileSidebarOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Mobile overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <aside className={cn(
        "fixed top-0 left-0 z-50 h-full bg-white border-r border-gray-200 transition-transform duration-300 md:hidden w-64",
        mobileSidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="h-16 border-b border-gray-200 flex items-center justify-between px-4">
          <span className="font-semibold text-gray-900">VNA Server</span>
          <button onClick={() => setMobileSidebarOpen(false)} className="p-2 hover:bg-gray-100 rounded-md" aria-label="Close sidebar">
            <X size={20} />
          </button>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          <NavLinks location={location} sidebarOpen onItemClick={() => setMobileSidebarOpen(false)} />
        </nav>
      </aside>

      {/* Desktop sidebar */}
      <aside className={cn(
        "hidden md:flex bg-white border-r border-gray-200 transition-all duration-300 flex-col shrink-0",
        sidebarOpen ? "w-64" : "w-16"
      )}>
        <div className="h-16 border-b border-gray-200 flex items-center px-4">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 hover:bg-gray-100 rounded-md" aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}>
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          {sidebarOpen && <span className="ml-3 font-semibold text-gray-900">VNA Server</span>}
        </div>

        <nav className="flex-1 p-2 space-y-1">
          <NavLinks location={location} sidebarOpen onItemClick={() => {}} />
        </nav>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 border-b border-gray-200 bg-white flex items-center px-4 md:px-6 gap-3">
          <button
            onClick={() => setMobileSidebarOpen(true)}
            className="p-2 hover:bg-gray-100 rounded-md md:hidden"
            aria-label="Open sidebar"
          >
            <Menu size={20} />
          </button>
          <span className="text-lg font-medium text-gray-900 truncate">{currentPage}</span>
          <div className="ml-auto flex items-center space-x-4 shrink-0">
            <div className="h-2 w-2 rounded-full bg-green-500" />
            <span className="text-sm text-gray-600 hidden sm:inline">System Online</span>
          </div>
        </header>

        <main className="flex-1 p-4 md:p-6">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

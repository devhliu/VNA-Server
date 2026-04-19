import * as React from "react"

interface TabsProps {
  value?: string
  onValueChange?: (value: string) => void
  children: React.ReactNode
  className?: string
}

function Tabs({ value, onValueChange, children, className }: TabsProps) {
  return (
    <div className={className} data-value={value}>
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<any>, { value, onValueChange })
        }
        return child
      })}
    </div>
  )
}

function TabsList({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement> & { value?: string; onValueChange?: (v: string) => void }) {
  return (
    <div className={`inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground ${className || ""}`}>
      {children}
    </div>
  )
}

function TabsTrigger({ value, className, children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { value?: string; onValueChange?: (v: string) => void }) {
  const contextValue = (props as any).value as string | undefined
  const onValueChange = (props as any).onValueChange as ((v: string) => void) | undefined
  const isActive = contextValue === value
  return (
    <button
      className={`inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${isActive ? "bg-background text-foreground shadow" : "hover:bg-background/50"}`}
      onClick={() => onValueChange?.(value || "")}
    >
      {children}
    </button>
  )
}

export { Tabs, TabsList, TabsTrigger }

import type { PropsWithChildren } from 'react'
import './video.css'

export default function VideoGrid({ children }: PropsWithChildren) {
  return <div className="videoGrid">{children}</div>
}

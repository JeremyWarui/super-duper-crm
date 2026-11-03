import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
// Fonts are bundled (no Google Fonts request): faster on mobile data, works offline
import '@fontsource-variable/public-sans'
import '@fontsource-variable/bricolage-grotesque'
import '@/styles/globals.css'
import { BrandingProvider } from '@/theme/branding'
import { router } from './router'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrandingProvider>
      <RouterProvider router={router} />
    </BrandingProvider>
  </StrictMode>,
)

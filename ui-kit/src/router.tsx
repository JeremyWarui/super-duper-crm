import { createBrowserRouter } from 'react-router-dom'
import { PublicLayout } from '@/components/layout/PublicLayout'
import { AppLayout } from '@/components/layout/AppLayout'
import { HomePage } from '@/routes/public/HomePage'
import { MembersPage } from '@/routes/crm/MembersPage'
import { KitPage } from '@/routes/KitPage'

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/kit', element: <KitPage /> },
    ],
  },
  {
    path: '/crm',
    element: <AppLayout kind="crm" />,
    children: [{ path: 'members', element: <MembersPage /> }, { index: true, element: <MembersPage /> }],
  },
])

import { Routes, Route, Navigate } from 'react-router-dom'
import Upload from './pages/Upload/Upload'
import Viewer from './pages/Viewer/Viewer'
import Loadout from './pages/Loadout/Loadout'
import Admin  from './pages/Admin/Admin'

export default function App() {
  return (
    <Routes>
      <Route path="/"           element={<Upload />} />
      <Route path="/viewer/:id" element={<Viewer />} />
      <Route path="/loadout/:demoId" element={<Loadout />} />
      <Route path="/admin"      element={<Admin />} />
      <Route path="*"           element={<Navigate to="/" replace />} />
    </Routes>
  )
}

import { Routes, Route, Navigate } from 'react-router-dom'
import Upload from './pages/Upload/Upload'
import Loadout from './pages/Loadout/Loadout'
import Results from './pages/Results/Results'
import MapPage from './pages/Map/MapPage'
import AimPage from './pages/Aim/AimPage'
import Admin  from './pages/Admin/Admin'

export default function App() {
  return (
    <Routes>
      <Route path="/"             element={<Upload />} />
      <Route path="/loadout/:demoId" element={<Loadout />} />
      <Route path="/results/:demoId" element={<Results />} />
      <Route path="/map/:demoId"   element={<MapPage />} />
      <Route path="/aim/:demoId"   element={<AimPage />} />
      <Route path="/admin"        element={<Admin />} />
      <Route path="*"             element={<Navigate to="/" replace />} />
    </Routes>
  )
}

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, RequireStaff } from './auth';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import ModelDetail from './pages/ModelDetail';
import ModelList from './pages/ModelList';

export default function App() {
  return (
    <BrowserRouter basename="/admin">
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<RequireStaff><Layout /></RequireStaff>}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/models/:name" element={<ModelList />} />
            <Route path="/models/:name/new" element={<ModelDetail mode="new" />} />
            <Route path="/models/:name/:id" element={<ModelDetail mode="view" />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

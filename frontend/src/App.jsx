import { Navigate, Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Skills from "./pages/Skills";
import Explore from "./pages/Explore";
import Requests from "./pages/Requests";
import Sessions from "./pages/Sessions";
import AIPicks from "./pages/AIPicks";
import Profile from "./pages/Profile";
import Admin from "./pages/Admin";
import SkillTestPage from "./pages/SkillTestPage";

function RequireAuth({ children, adminOnly = false }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "ADMIN") return <Navigate to="/" replace />;
  return (
    <>
      <Navbar />
      {children}
    </>
  );
}

function GuestOnly({ children }) {
  const { user } = useAuth();
  return user ? <Navigate to="/" replace /> : children;
}

function Home() {
  const { user } = useAuth();
  return user?.role === "ADMIN" ? <Navigate to="/admin" replace /> : <Dashboard />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
      <Route path="/register" element={<GuestOnly><Register /></GuestOnly>} />
      <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
      <Route path="/skills" element={<RequireAuth><Skills /></RequireAuth>} />
      <Route path="/skills/:skillId/test" element={<RequireAuth><SkillTestPage /></RequireAuth>} />
      <Route path="/explore" element={<RequireAuth><Explore /></RequireAuth>} />
      <Route path="/requests" element={<RequireAuth><Requests /></RequireAuth>} />
      <Route path="/sessions" element={<RequireAuth><Sessions /></RequireAuth>} />
      <Route path="/ai-picks" element={<RequireAuth><AIPicks /></RequireAuth>} />
      <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
      <Route path="/admin" element={<RequireAuth adminOnly><Admin /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

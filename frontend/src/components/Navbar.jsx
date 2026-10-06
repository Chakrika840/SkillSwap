import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { initial } from "../utils";

const USER_LINKS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/skills", label: "Skills" },
  { to: "/explore", label: "Explore" },
  { to: "/requests", label: "Requests" },
  { to: "/sessions", label: "Sessions" },
  { to: "/ai-picks", label: "AI Picks" },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const links = user.role === "ADMIN" ? [{ to: "/admin", label: "Admin" }] : USER_LINKS;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <header className="navbar">
      <NavLink to="/" className="brand">SkillSwap</NavLink>
      <nav className="nav-links" aria-label="Main">
        {links.map((link) => (
          <NavLink key={link.to} to={link.to} end={link.end}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            {link.label}
          </NavLink>
        ))}
      </nav>
      <div className="nav-user">
        <NavLink to="/profile" className="nav-profile" title="Your profile">
          <span className="avatar avatar-sm" aria-hidden="true">{initial(user.name)}</span>
          <span className="nav-name">{user.name}</span>
        </NavLink>
        <button type="button" className="btn btn-ghost btn-sm" onClick={handleLogout}>Log out</button>
      </div>
    </header>
  );
}

import { Link, NavLink, Route, Routes } from "react-router-dom";

import { useServerWarmup } from "./hooks/useServerWarmup.js";
import AnalyzePage from "./pages/AnalyzePage.jsx";
import ComparePage from "./pages/ComparePage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";

function Wordmark() {
  return (
    <Link to="/" className="wordmark">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="16" r="11" fill="none" stroke="var(--rule)" strokeWidth="5" />
        <path d="M16 5a11 11 0 1 1-10.46 14.4" fill="none" stroke="var(--accent)" strokeWidth="5" strokeLinecap="round" />
      </svg>
      JobFit
    </Link>
  );
}

function NotFoundPage() {
  return (
    <div className="empty">
      <h1>Page not found</h1>
      <p>That address doesn't match any page.</p>
      <Link to="/">Go to Analyze</Link>
    </div>
  );
}

export default function App() {
  useServerWarmup();

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="site-header__inner">
          <Wordmark />
          <nav aria-label="Main">
            <ul className="site-nav">
              <li>
                <NavLink to="/" end>
                  Analyze
                </NavLink>
              </li>
              <li>
                <NavLink to="/history">History</NavLink>
              </li>
              <li>
                <NavLink to="/compare">Compare</NavLink>
              </li>
            </ul>
          </nav>
        </div>
      </header>
      <main id="main" className="page">
        <Routes>
          <Route path="/" element={<AnalyzePage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </>
  );
}

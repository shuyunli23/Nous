import { Navigate } from 'react-router-dom';

/** Modes live under Settings; keep this path so old links still work. */
export default function ModesPage() {
  return <Navigate to="/settings#modes" replace />;
}

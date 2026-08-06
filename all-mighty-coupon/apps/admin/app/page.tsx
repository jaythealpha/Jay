import AdminDashboard from './admin-dashboard';
import type { HealthResponseDto } from './types';

const API_BASE_URL = process.env.ADMIN_API_BASE_URL ?? 'http://localhost:3001';
// Browser-side base URL for the dashboard (client component fetches directly).
const PUBLIC_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:3001';

async function fetchHealth(): Promise<HealthResponseDto | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { cache: 'no-store' });
    if (!res.ok) return null;
    return (await res.json()) as HealthResponseDto;
  } catch {
    // The admin page must render even when the API is down; the UI shows the
    // unreachable state instead of crashing the build or the request.
    return null;
  }
}

export default async function AdminHomePage() {
  const health = await fetchHealth();

  return (
    <main style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
      <h1 style={{ fontSize: 24 }}>All Mighty Coupon — 운영자 콘솔</h1>
      <p style={{ color: '#5A6360' }}>
        Milestone 0 기반 화면입니다. 쿠폰 운영 기능은 이후 마일스톤에서 추가됩니다.
      </p>
      <section
        style={{
          background: '#FFFFFF',
          border: '1px solid #DCE3E0',
          borderRadius: 12,
          padding: 16,
        }}
      >
        <h2 style={{ fontSize: 16, marginTop: 0 }}>API 상태</h2>
        {health === null ? (
          <p role="status">⚠️ API에 연결할 수 없습니다 ({API_BASE_URL})</p>
        ) : (
          <ul style={{ paddingLeft: 20 }}>
            <li>전체 상태: {health.status === 'ok' ? '✅ 정상' : '⚠️ 성능 저하'}</li>
            <li>
              데이터베이스: {health.components.database === 'up' ? '✅ 연결됨' : '❌ 연결 안 됨'}
            </li>
            <li>Redis: {health.components.redis === 'up' ? '✅ 연결됨' : '❌ 연결 안 됨'}</li>
            <li>확인 시각(UTC): {health.checkedAt}</li>
          </ul>
        )}
      </section>
      <AdminDashboard apiBaseUrl={PUBLIC_API_BASE_URL} />
    </main>
  );
}

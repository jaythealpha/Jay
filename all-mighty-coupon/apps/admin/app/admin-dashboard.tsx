'use client';

import { useCallback, useState } from 'react';
import type { AdminStatsDto } from './types';

const STATUS_LABELS: Record<string, string> = {
  PROCESSING: '분석 중',
  NEEDS_REVIEW: '확인 필요',
  ACTIVE: '사용 가능',
  EXPIRING_SOON: '곧 만료',
  EXPIRED: '만료',
  REDEEMED: '사용 완료',
  ARCHIVED: '보관',
  INVALID: '인식 실패',
};

const card: React.CSSProperties = {
  background: '#FFFFFF',
  border: '1px solid #DCE3E0',
  borderRadius: 12,
  padding: 16,
  marginTop: 16,
};

/**
 * Operator dashboard: counts only — no user emails, no coupon contents, and
 * never barcode material (spec §17). The ops token stays in memory only.
 */
export default function AdminDashboard({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [token, setToken] = useState('');
  const [stats, setStats] = useState<AdminStatsDto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/v1/admin/stats`, {
        headers: { 'x-admin-token': token },
        cache: 'no-store',
      });
      if (res.status === 401) {
        setError('운영자 토큰이 올바르지 않습니다.');
        setStats(null);
        return;
      }
      if (res.status === 503) {
        setError('관리자 API가 비활성화되어 있습니다 (ADMIN_API_TOKEN 미설정).');
        setStats(null);
        return;
      }
      if (!res.ok) {
        setError(`요청 실패 (${res.status})`);
        return;
      }
      setStats((await res.json()) as AdminStatsDto);
    } catch {
      setError('API에 연결할 수 없습니다.');
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, token]);

  return (
    <section>
      <div style={card}>
        <h2 style={{ fontSize: 16, marginTop: 0 }}>운영자 인증</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="ADMIN_API_TOKEN"
            aria-label="운영자 토큰"
            style={{
              flex: 1,
              padding: '10px 12px',
              border: '1px solid #DCE3E0',
              borderRadius: 8,
            }}
          />
          <button
            onClick={load}
            disabled={loading || token.length === 0}
            style={{
              padding: '10px 20px',
              borderRadius: 8,
              border: 'none',
              background: '#1B5E4A',
              color: '#fff',
              cursor: 'pointer',
              minHeight: 44,
            }}
          >
            {loading ? '조회 중...' : '통계 조회'}
          </button>
        </div>
        {error && <p style={{ color: '#B3261E' }}>{error}</p>}
      </div>

      {stats && (
        <>
          <div style={card}>
            <h2 style={{ fontSize: 16, marginTop: 0 }}>요약</h2>
            <ul style={{ paddingLeft: 20 }}>
              <li>가입 사용자: {stats.users}명</li>
              <li>푸시 등록 기기: {stats.pushDevices}대</li>
              <li>
                알림 — 대기 {stats.notifications.pending} / 발송 {stats.notifications.sent} / 취소{' '}
                {stats.notifications.cancelled}
              </li>
              <li>기준 시각(UTC): {stats.generatedAt}</li>
            </ul>
          </div>

          <div style={card}>
            <h2 style={{ fontSize: 16, marginTop: 0 }}>쿠폰 상태 분포</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <tbody>
                {Object.entries(stats.couponsByStatus).map(([status, count]) => (
                  <tr key={status} style={{ borderBottom: '1px solid #EEF2F0' }}>
                    <td style={{ padding: '6px 0' }}>
                      {STATUS_LABELS[status] ?? status}{' '}
                      <span style={{ color: '#5A6360' }}>({status})</span>
                    </td>
                    <td style={{ textAlign: 'right' }}>{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={card}>
            <h2 style={{ fontSize: 16, marginTop: 0 }}>최근 도메인 이벤트 (20)</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <tbody>
                {stats.recentEvents.map((event, index) => (
                  <tr key={index} style={{ borderBottom: '1px solid #EEF2F0' }}>
                    <td style={{ padding: '4px 0' }}>{event.type}</td>
                    <td style={{ color: '#5A6360' }}>{event.couponId.slice(0, 10)}…</td>
                    <td style={{ textAlign: 'right', color: '#5A6360' }}>
                      {event.createdAt.replace('T', ' ').slice(0, 19)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

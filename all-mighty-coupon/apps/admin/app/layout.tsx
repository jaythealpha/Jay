import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'All Mighty Coupon Admin',
  description: 'Operator console for All Mighty Coupon',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body
        style={{
          fontFamily: "'Pretendard', 'Noto Sans KR', sans-serif",
          margin: 0,
          background: '#F6F8F7',
          color: '#1A1D1C',
        }}
      >
        {children}
      </body>
    </html>
  );
}

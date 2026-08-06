import 'package:amc_mobile/shared/utilities/d_day.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final now = DateTime(2026, 8, 6, 14, 0);

  group('daysUntilExpiration', () {
    test('expiring later today is 0, not 1', () {
      expect(daysUntilExpiration(DateTime(2026, 8, 6, 23, 59), now), 0);
    });

    test('counts calendar days, not 24h periods', () {
      // 10 hours away but across midnight -> next calendar day.
      expect(daysUntilExpiration(DateTime(2026, 8, 7, 0, 30), now), 1);
      expect(daysUntilExpiration(DateTime(2026, 8, 9, 1, 0), now), 3);
    });

    test('is negative after expiry and null without a date', () {
      expect(daysUntilExpiration(DateTime(2026, 8, 5), now), -1);
      expect(daysUntilExpiration(null, now), isNull);
    });
  });

  group('dDayLabel', () {
    test('renders D-DAY, D-n, 만료됨, 기한 없음', () {
      expect(dDayLabel(DateTime(2026, 8, 6, 23), now), 'D-DAY');
      expect(dDayLabel(DateTime(2026, 8, 9), now), 'D-3');
      expect(dDayLabel(DateTime(2026, 8, 1), now), '만료됨');
      expect(dDayLabel(null, now), '기한 없음');
    });
  });
}

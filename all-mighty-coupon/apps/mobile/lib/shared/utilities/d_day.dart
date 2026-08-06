/// D-day helpers shared by every screen so "days left" is computed one way.
/// Calendar-day based: expiring later today is D-DAY, not D-1.
int? daysUntilExpiration(DateTime? expiresAt, DateTime now) {
  if (expiresAt == null) return null;
  final expiresLocal = expiresAt.toLocal();
  final nowLocal = now.toLocal();
  final expiresDay =
      DateTime(expiresLocal.year, expiresLocal.month, expiresLocal.day);
  final nowDay = DateTime(nowLocal.year, nowLocal.month, nowLocal.day);
  return expiresDay.difference(nowDay).inDays;
}

String dDayLabel(DateTime? expiresAt, DateTime now) {
  final days = daysUntilExpiration(expiresAt, now);
  if (days == null) return '기한 없음';
  if (days < 0) return '만료됨';
  if (days == 0) return 'D-DAY';
  return 'D-$days';
}

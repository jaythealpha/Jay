import 'package:flutter/material.dart';

import '../../../app/theme/app_theme.dart';
import '../../../shared/models/coupon_summary.dart';
import '../../../shared/utilities/d_day.dart';

/// Information priority on a card (spec §20):
/// brand > product > days left > value > status.
class CouponCard extends StatelessWidget {
  const CouponCard({super.key, required this.coupon, this.now});

  final CouponSummary coupon;
  final DateTime? now;

  @override
  Widget build(BuildContext context) {
    final reference = now ?? DateTime.now();
    final label = dDayLabel(coupon.expiresAt, reference);
    final statusInfo = _statusInfo(coupon.status);

    return Card(
      color: AmcColors.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AmcColors.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    coupon.brandName ?? '브랜드 미확인',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: AmcColors.textPrimary,
                    ),
                  ),
                ),
                Text(
                  label,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: label == '만료됨'
                        ? AmcColors.statusExpired
                        : AmcColors.statusExpiringSoon,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              coupon.productName ?? '상품명 미확인',
              style: const TextStyle(color: AmcColors.textSecondary),
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                if (coupon.faceValueMinor != null)
                  Text(
                    '${_formatAmount(coupon.faceValueMinor!)}원',
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      color: AmcColors.textPrimary,
                    ),
                  )
                else
                  const SizedBox.shrink(),
                Semantics(
                  label: '상태: ${statusInfo.label}',
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(statusInfo.icon, size: 16, color: statusInfo.color),
                      const SizedBox(width: 4),
                      Text(
                        statusInfo.label,
                        style: TextStyle(fontSize: 12, color: statusInfo.color),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  static String _formatAmount(int amount) {
    final digits = amount.toString();
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(',');
      buffer.write(digits[i]);
    }
    return buffer.toString();
  }

  static ({IconData icon, String label, Color color}) _statusInfo(String status) {
    switch (status) {
      case 'ACTIVE':
        return (icon: Icons.check_circle_outline, label: '사용 가능', color: AmcColors.statusActive);
      case 'EXPIRING_SOON':
        return (icon: Icons.timer_outlined, label: '곧 만료', color: AmcColors.statusExpiringSoon);
      case 'EXPIRED':
        return (icon: Icons.block_outlined, label: '만료', color: AmcColors.statusExpired);
      case 'REDEEMED':
        return (icon: Icons.done_all_outlined, label: '사용 완료', color: AmcColors.statusRedeemed);
      case 'NEEDS_REVIEW':
        return (icon: Icons.help_outline, label: '확인 필요', color: AmcColors.statusNeedsReview);
      default:
        return (icon: Icons.hourglass_empty, label: '처리 중', color: AmcColors.textSecondary);
    }
  }
}

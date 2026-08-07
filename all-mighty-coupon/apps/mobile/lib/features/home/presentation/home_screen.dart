import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_theme.dart';
import '../../../core/auth/auth_controller.dart';
import '../../../core/errors/app_exception.dart';
import '../../../shared/models/coupon_summary.dart';
import '../../../shared/utilities/d_day.dart';
import '../data/health_api.dart';
import '../data/home_api.dart';

/// Action-first home (spec §13): what should the user do RIGHT NOW —
/// 곧 만료돼요 → 이번 주 사용하세요 → 최근 등록 → 내 쿠폰 요약.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summary = ref.watch(homeSummaryProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('All Mighty Coupon'),
        actions: [
          IconButton(
            tooltip: '만료 알림',
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () => context.go('/notifications'),
          ),
          IconButton(
            tooltip: '로그아웃',
            icon: const Icon(Icons.logout_outlined),
            onPressed: () => ref.read(authControllerProvider.notifier).logout(),
          ),
        ],
      ),
      body: summary.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                error is AppException ? error.userMessage : '홈 정보를 불러오지 못했어요.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              SizedBox(
                height: 48,
                child: FilledButton(
                  onPressed: () => ref.invalidate(homeSummaryProvider),
                  child: const Text('다시 시도'),
                ),
              ),
            ],
          ),
        ),
        data: (data) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(homeSummaryProvider),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (data.expiringSoon.isNotEmpty) ...[
                const _SectionTitle('곧 만료돼요 ⏰'),
                for (final coupon in data.expiringSoon)
                  _MiniCouponTile(coupon: coupon, highlightDday: true),
                const SizedBox(height: 16),
              ],
              if (data.useThisWeek.isNotEmpty) ...[
                const _SectionTitle('이번 주 사용하세요'),
                for (final coupon in data.useThisWeek) _MiniCouponTile(coupon: coupon),
                const SizedBox(height: 16),
              ],
              if (data.recent.isNotEmpty) ...[
                const _SectionTitle('최근 등록'),
                for (final coupon in data.recent) _MiniCouponTile(coupon: coupon),
                const SizedBox(height: 16),
              ],
              const _SectionTitle('내 쿠폰 요약'),
              _SummaryCard(data: data),
              const SizedBox(height: 24),
              SizedBox(
                height: 52,
                child: FilledButton.icon(
                  onPressed: () => context.go('/capture'),
                  icon: const Icon(Icons.add_a_photo_outlined),
                  label: const Text('쿠폰 등록'),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                height: 52,
                child: OutlinedButton.icon(
                  onPressed: () => context.go('/wallet'),
                  icon: const Icon(Icons.wallet_outlined),
                  label: const Text('쿠폰함 열기'),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                height: 52,
                child: OutlinedButton.icon(
                  onPressed: () => context.go('/market'),
                  icon: const Icon(Icons.storefront_outlined),
                  label: const Text('쿠폰 마켓 (테스트)'),
                ),
              ),
              const SizedBox(height: 24),
              if (data.counts.total == 0)
                const Center(
                  child: Text(
                    '첫 쿠폰을 등록해 보세요!\nNever Lose a Coupon Again.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AmcColors.textSecondary),
                  ),
                ),
              const _HealthFooter(),
            ],
          ),
        ),
      ),
    );
  }
}

class _HealthFooter extends ConsumerWidget {
  const _HealthFooter();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final health = ref.watch(healthProvider);
    final (icon, text, color) = health.when(
      loading: () => (Icons.sync, '서버 상태 확인 중...', AmcColors.textSecondary),
      error: (_, _) => (Icons.cloud_off, '서버에 연결할 수 없어요', AmcColors.danger),
      data: (status) => status.overall == 'ok'
          ? (Icons.check_circle_outline, '서버 연결됨', AmcColors.statusActive)
          : (Icons.warning_amber_outlined, '서버 상태 저하', AmcColors.statusExpiringSoon),
    );
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(text, style: TextStyle(fontSize: 12, color: color)),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.bold,
          color: AmcColors.textPrimary,
        ),
      ),
    );
  }
}

class _MiniCouponTile extends StatelessWidget {
  const _MiniCouponTile({required this.coupon, this.highlightDday = false});

  final CouponSummary coupon;
  final bool highlightDday;

  @override
  Widget build(BuildContext context) {
    final label = dDayLabel(coupon.expiresAt, DateTime.now());
    return Card(
      color: AmcColors.surface,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: const BorderSide(color: AmcColors.border),
      ),
      child: ListTile(
        onTap: () => context.go('/coupon/${coupon.id}'),
        title: Text(
          coupon.brandName ?? '브랜드 미확인',
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
        ),
        subtitle: Text(
          coupon.productName ?? '상품명 미확인',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 13, color: AmcColors.textSecondary),
        ),
        trailing: Text(
          label,
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: highlightDday ? AmcColors.statusExpiringSoon : AmcColors.textSecondary,
          ),
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.data});

  final HomeSummary data;

  static String _formatAmount(int amount) {
    final digits = amount.toString();
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(',');
      buffer.write(digits[i]);
    }
    return buffer.toString();
  }

  @override
  Widget build(BuildContext context) {
    final counts = data.counts;
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
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _CountChip(label: '사용 가능', value: counts.active),
                _CountChip(label: '곧 만료', value: counts.expiringSoon),
                _CountChip(label: '사용 완료', value: counts.redeemed),
                _CountChip(label: '확인 필요', value: counts.needsReview),
              ],
            ),
            const Divider(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('총 ${counts.total}개 쿠폰',
                    style: const TextStyle(color: AmcColors.textSecondary)),
                Text(
                  '${_formatAmount(data.totalValueMinor)}원',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _CountChip extends StatelessWidget {
  const _CountChip({required this.label, required this.value});

  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text('$value',
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        Text(label, style: const TextStyle(fontSize: 12, color: AmcColors.textSecondary)),
      ],
    );
  }
}

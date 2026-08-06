import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_theme.dart';
import '../../../core/errors/app_exception.dart';
import '../data/health_api.dart';

/// Milestone 0 foundation screen: verifies live API connectivity and opens
/// the wallet. The real home (만료 우선 추천) arrives in later milestones.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final health = ref.watch(healthProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('All Mighty Coupon')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Never Lose a Coupon Again.',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: AmcColors.textPrimary,
              ),
            ),
            const SizedBox(height: 16),
            Card(
              color: AmcColors.surface,
              elevation: 0,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: const BorderSide(color: AmcColors.border),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: health.when(
                  loading: () => const Row(
                    children: [
                      SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      SizedBox(width: 12),
                      Text('서버 상태 확인 중...'),
                    ],
                  ),
                  error: (error, _) => Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.cloud_off, color: AmcColors.danger),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              error is AppException
                                  ? error.userMessage
                                  : '서버 상태를 확인하지 못했어요.',
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      SizedBox(
                        height: 48,
                        child: TextButton(
                          onPressed: () => ref.invalidate(healthProvider),
                          child: const Text('다시 시도'),
                        ),
                      ),
                    ],
                  ),
                  data: (status) => Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            status.overall == 'ok'
                                ? Icons.check_circle
                                : Icons.warning_amber,
                            color: status.overall == 'ok'
                                ? AmcColors.statusActive
                                : AmcColors.statusExpiringSoon,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            status.overall == 'ok' ? '서버 연결됨' : '서버 상태 저하',
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '데이터베이스 ${status.database == 'up' ? '정상' : '오류'} · '
                        'Redis ${status.redis == 'up' ? '정상' : '오류'}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AmcColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              height: 52,
              child: FilledButton.icon(
                onPressed: () => context.go('/wallet'),
                icon: const Icon(Icons.wallet_outlined),
                label: const Text('쿠폰함 열기'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

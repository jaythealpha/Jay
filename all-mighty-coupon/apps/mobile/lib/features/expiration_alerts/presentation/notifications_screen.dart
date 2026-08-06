import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_theme.dart';
import '../../../core/errors/app_exception.dart';
import '../../coupon_detail/data/coupon_actions_api.dart';
import '../data/notifications_api.dart';

/// In-app expiration reminder feed. Every entry deep-links to its coupon and
/// offers the spec §16 actions: 쿠폰 보기 / 사용 완료 / 하루 뒤 다시 알림.
class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feed = ref.watch(notificationFeedProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('만료 알림')),
      body: feed.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                error is AppException ? error.userMessage : '알림을 불러오지 못했어요.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              SizedBox(
                height: 48,
                child: FilledButton(
                  onPressed: () => ref.invalidate(notificationFeedProvider),
                  child: const Text('다시 시도'),
                ),
              ),
            ],
          ),
        ),
        data: (items) {
          if (items.isEmpty) {
            return const Center(child: Text('아직 도착한 만료 알림이 없어요.'));
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(notificationFeedProvider),
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: items.length,
              itemBuilder: (context, index) => _NotificationCard(item: items[index]),
            ),
          );
        },
      ),
    );
  }
}

class _NotificationCard extends ConsumerWidget {
  const _NotificationCard({required this.item});

  final ExpirationNotification item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
              children: [
                const Icon(Icons.notifications_active_outlined,
                    size: 18, color: AmcColors.statusExpiringSoon),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(item.message, style: const TextStyle(fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              item.sentAt.toLocal().toString().substring(0, 16),
              style: const TextStyle(fontSize: 12, color: AmcColors.textSecondary),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                SizedBox(
                  height: 44,
                  child: FilledButton.tonal(
                    onPressed: () => context.go('/coupon/${item.couponId}'),
                    child: const Text('쿠폰 보기'),
                  ),
                ),
                SizedBox(
                  height: 44,
                  child: OutlinedButton(
                    onPressed: () async {
                      try {
                        await ref.read(couponActionsApiProvider).redeem(item.couponId);
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('사용 완료로 처리했어요.')),
                          );
                        }
                      } on AppException catch (error) {
                        if (context.mounted) {
                          ScaffoldMessenger.of(context)
                              .showSnackBar(SnackBar(content: Text(error.userMessage)));
                        }
                      }
                    },
                    child: const Text('사용 완료'),
                  ),
                ),
                SizedBox(
                  height: 44,
                  child: TextButton(
                    onPressed: () async {
                      await ref.read(notificationsApiProvider).snooze(item.id);
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('내일 다시 알려드릴게요.')),
                        );
                      }
                    },
                    child: const Text('하루 뒤 다시 알림'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

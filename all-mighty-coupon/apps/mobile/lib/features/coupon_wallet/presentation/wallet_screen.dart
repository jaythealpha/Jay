import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_theme.dart';
import '../../../core/errors/app_exception.dart';
import '../application/coupon_list_controller.dart';
import 'coupon_card.dart';

class WalletScreen extends ConsumerWidget {
  const WalletScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(couponListProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('쿠폰함')),
      body: state.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => _ErrorView(
          message: error is AppException
              ? error.userMessage
              : '알 수 없는 오류가 발생했어요.',
          onRetry: () => ref.read(couponListProvider.notifier).refresh(),
        ),
        data: (result) {
          if (result.coupons.isEmpty) {
            return const Center(child: Text('등록된 쿠폰이 아직 없어요.'));
          }
          return Column(
            children: [
              if (result.fromCache)
                Container(
                  width: double.infinity,
                  color: AmcColors.primaryLight,
                  padding: const EdgeInsets.all(8),
                  child: Text(
                    '오프라인 — 마지막 동기화 데이터를 보여드려요'
                    '${result.syncedAt != null ? ' (${result.syncedAt!.toLocal().toString().substring(0, 16)})' : ''}',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 12, color: AmcColors.textSecondary),
                  ),
                ),
              Expanded(
                child: RefreshIndicator(
                  onRefresh: () => ref.read(couponListProvider.notifier).refresh(),
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: result.coupons.length,
                    itemBuilder: (context, index) =>
                        CouponCard(coupon: result.coupons[index]),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.wifi_off_outlined, size: 48, color: AmcColors.textSecondary),
          const SizedBox(height: 12),
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 16),
          // 44pt minimum touch target (spec §19).
          SizedBox(
            height: 48,
            child: FilledButton(
              onPressed: onRetry,
              child: const Text('다시 시도'),
            ),
          ),
        ],
      ),
    );
  }
}

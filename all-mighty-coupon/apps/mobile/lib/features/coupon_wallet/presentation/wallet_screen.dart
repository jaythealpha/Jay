import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_theme.dart';
import '../../../core/errors/app_exception.dart';
import '../application/coupon_list_controller.dart';
import 'coupon_card.dart';

const _statusFilters = <(String label, String? status)>[
  ('전체', null),
  ('사용 가능', 'ACTIVE'),
  ('곧 만료', 'EXPIRING_SOON'),
  ('만료', 'EXPIRED'),
  ('사용 완료', 'REDEEMED'),
  ('확인 필요', 'NEEDS_REVIEW'),
];

const _sortOptions = <(String label, String value)>[
  ('유효기간 빠른 순', 'EXPIRATION_ASC'),
  ('최근 등록 순', 'CREATED_DESC'),
  ('금액 높은 순', 'VALUE_DESC'),
  ('브랜드 순', 'BRAND_ASC'),
];

class WalletScreen extends ConsumerWidget {
  const WalletScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(couponListProvider);
    final query = ref.watch(walletQueryProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('쿠폰함'),
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.sort),
            tooltip: '정렬',
            onSelected: (value) => ref.read(walletQueryProvider.notifier).setSort(value),
            itemBuilder: (context) => [
              for (final (label, value) in _sortOptions)
                PopupMenuItem(
                  value: value,
                  child: Row(
                    children: [
                      if (query.sort == value)
                        const Icon(Icons.check, size: 16)
                      else
                        const SizedBox(width: 16),
                      const SizedBox(width: 8),
                      Text(label),
                    ],
                  ),
                ),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: TextField(
              onSubmitted: (value) => ref.read(walletQueryProvider.notifier).setSearch(value),
              decoration: InputDecoration(
                hintText: '브랜드, 상품명, 카테고리 검색',
                prefixIcon: const Icon(Icons.search),
                isDense: true,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
              ),
              textInputAction: TextInputAction.search,
            ),
          ),
          SizedBox(
            height: 56,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              children: [
                for (final (label, status) in _statusFilters)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      label: Text(label),
                      selected: query.status == status,
                      onSelected: (_) =>
                          ref.read(walletQueryProvider.notifier).setStatus(status),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: state.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => _ErrorView(
                message: error is AppException
                    ? error.userMessage
                    : '알 수 없는 오류가 발생했어요.',
                onRetry: () => ref.read(couponListProvider.notifier).refresh(),
              ),
              data: (result) {
                if (result.coupons.isEmpty) {
                  return Center(
                    child: Text(
                      query.q.isNotEmpty || query.status != null
                          ? '조건에 맞는 쿠폰이 없어요.'
                          : '등록된 쿠폰이 아직 없어요.',
                    ),
                  );
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
                          style: const TextStyle(
                            fontSize: 12,
                            color: AmcColors.textSecondary,
                          ),
                        ),
                      ),
                    Expanded(
                      child: RefreshIndicator(
                        onRefresh: () => ref.read(couponListProvider.notifier).refresh(),
                        child: ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: result.coupons.length,
                          itemBuilder: (context, index) {
                            final coupon = result.coupons[index];
                            return InkWell(
                              onTap: () => context.go('/coupon/${coupon.id}'),
                              child: CouponCard(coupon: coupon),
                            );
                          },
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ],
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

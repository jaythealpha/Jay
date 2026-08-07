import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_theme.dart';
import '../../../core/errors/app_exception.dart';
import '../../../shared/utilities/d_day.dart';
import '../data/market_api.dart';

final _marketSearchProvider = NotifierProvider<_MarketSearchController, String>(
  _MarketSearchController.new,
);

class _MarketSearchController extends Notifier<String> {
  @override
  String build() => '';

  void set(String value) => state = value;
}

/// C2C coupon market (M4). Purchases run on the MOCK payment provider —
/// the UI says so explicitly so simulated buying never looks like real money.
class MarketScreen extends ConsumerWidget {
  const MarketScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final q = ref.watch(_marketSearchProvider);
    final listings = ref.watch(marketListingsProvider(q));

    return Scaffold(
      appBar: AppBar(title: const Text('쿠폰 마켓')),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            color: AmcColors.primaryLight,
            padding: const EdgeInsets.all(8),
            child: const Text(
              '테스트 마켓 — 결제는 모의(MOCK)로 처리되며 실제 돈이 오가지 않아요',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: AmcColors.textSecondary),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: TextField(
              onSubmitted: (value) =>
                  ref.read(_marketSearchProvider.notifier).set(value.trim()),
              decoration: InputDecoration(
                hintText: '브랜드, 상품명 검색',
                prefixIcon: const Icon(Icons.search),
                isDense: true,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
              ),
              textInputAction: TextInputAction.search,
            ),
          ),
          Expanded(
            child: listings.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      error is AppException ? error.userMessage : '마켓을 불러오지 못했어요.',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 16),
                    SizedBox(
                      height: 48,
                      child: FilledButton(
                        onPressed: () => ref.invalidate(marketListingsProvider(q)),
                        child: const Text('다시 시도'),
                      ),
                    ),
                  ],
                ),
              ),
              data: (items) {
                if (items.isEmpty) {
                  return const Center(child: Text('판매 중인 쿠폰이 없어요.'));
                }
                return RefreshIndicator(
                  onRefresh: () async => ref.invalidate(marketListingsProvider(q)),
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: items.length,
                    itemBuilder: (context, index) =>
                        _ListingCard(listing: items[index], searchQuery: q),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _ListingCard extends ConsumerWidget {
  const _ListingCard({required this.listing, required this.searchQuery});

  final MarketListing listing;
  final String searchQuery;

  static String _amount(int value) {
    final digits = value.toString();
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(',');
      buffer.write(digits[i]);
    }
    return buffer.toString();
  }

  Future<void> _purchase(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('쿠폰을 구매할까요?'),
        content: Text(
          '${listing.coupon.brandName ?? '브랜드 미상'} · ${_amount(listing.priceMinor)}원\n'
          '결제는 모의(MOCK)로 처리됩니다 — 실제 청구 없음.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('구매'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(marketApiProvider).purchase(listing.id);
      ref.invalidate(marketListingsProvider(searchQuery));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('구매 완료! 쿠폰함에서 확인하세요.')),
        );
      }
    } on MarketException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.userMessage)));
      }
    } on AppException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.userMessage)));
      }
    }
  }

  Future<void> _cancel(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(marketApiProvider).cancelListing(listing.id);
      ref.invalidate(marketListingsProvider(searchQuery));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('판매를 취소했어요.')),
        );
      }
    } on MarketException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.userMessage)));
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final coupon = listing.coupon;
    return Card(
      color: AmcColors.surface,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 10),
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
                    coupon.brandName ?? '브랜드 미상',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                Text(
                  dDayLabel(coupon.expiresAt, DateTime.now()),
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    color: AmcColors.statusExpiringSoon,
                  ),
                ),
              ],
            ),
            Text(
              coupon.productName ?? '상품명 미상',
              style: const TextStyle(color: AmcColors.textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${_amount(listing.priceMinor)}원',
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    if (coupon.faceValueMinor != null)
                      Text(
                        '정가 ${_amount(coupon.faceValueMinor!)}원',
                        style: const TextStyle(fontSize: 12, color: AmcColors.textSecondary),
                      ),
                  ],
                ),
                if (listing.mine)
                  SizedBox(
                    height: 44,
                    child: OutlinedButton(
                      onPressed: () => _cancel(context, ref),
                      child: const Text('판매 취소'),
                    ),
                  )
                else
                  SizedBox(
                    height: 44,
                    child: FilledButton(
                      onPressed: () => _purchase(context, ref),
                      child: const Text('구매'),
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

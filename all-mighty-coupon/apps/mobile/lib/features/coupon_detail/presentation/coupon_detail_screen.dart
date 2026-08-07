import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_theme.dart';
import '../../../core/errors/app_exception.dart';
import '../../../shared/models/coupon_detail.dart';
import '../../../shared/utilities/d_day.dart';
import '../../market/data/market_api.dart';
import '../application/detail_controller.dart';

class CouponDetailScreen extends ConsumerWidget {
  const CouponDetailScreen({super.key, required this.couponId});

  final String couponId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(detailControllerProvider(couponId));

    return Scaffold(
      appBar: AppBar(title: const Text('쿠폰 상세')),
      body: state.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                error is AppException ? error.userMessage : '쿠폰을 불러오지 못했어요.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              SizedBox(
                height: 48,
                child: FilledButton(
                  onPressed: () => ref.invalidate(detailControllerProvider(couponId)),
                  child: const Text('다시 시도'),
                ),
              ),
            ],
          ),
        ),
        data: (detail) => _DetailBody(couponId: couponId, detail: detail),
      ),
    );
  }
}

class _DetailBody extends ConsumerWidget {
  const _DetailBody({required this.couponId, required this.detail});

  final String couponId;
  final CouponDetail detail;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summary = detail.summary;
    final now = DateTime.now();
    final thumbnail = detail.assets
        .where((a) => a.type == 'NORMALIZED' || a.type == 'ORIGINAL')
        .toList();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (thumbnail.isNotEmpty)
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.network(
              thumbnail.first.url,
              height: 220,
              fit: BoxFit.cover,
              // Signed URLs expire and offline mode has no network — degrade
              // to a placeholder instead of an error surface.
              errorBuilder: (context, error, stack) => Container(
                height: 120,
                color: AmcColors.primaryLight,
                alignment: Alignment.center,
                child: const Text('이미지를 불러올 수 없어요 (오프라인이거나 링크 만료)'),
              ),
            ),
          ),
        const SizedBox(height: 16),
        Text(
          summary.brandName ?? '브랜드 미확인',
          style: const TextStyle(fontSize: 14, color: AmcColors.textSecondary),
        ),
        Text(
          summary.productName ?? '상품명 미확인',
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 12),
        _InfoRow(label: '상태', value: statusLabel(summary.status)),
        _InfoRow(
          label: '유효기간',
          value: summary.expiresAt == null
              ? '기한 없음'
              : '${summary.expiresAt!.toLocal().toIso8601String().substring(0, 10)}'
                  ' (${dDayLabel(summary.expiresAt, now)})',
        ),
        if (summary.faceValueMinor != null)
          _InfoRow(label: '금액', value: '${_formatAmount(summary.faceValueMinor!)}원'),
        if (detail.usageLocationText != null)
          _InfoRow(label: '사용 가능 장소', value: detail.usageLocationText!),
        if (detail.usageConditions != null)
          _InfoRow(label: '이용 조건', value: detail.usageConditions!),
        _InfoRow(label: '등록 경로', value: summary.sourceType),
        _InfoRow(
          label: '등록일',
          value: summary.createdAt.toLocal().toIso8601String().substring(0, 10),
        ),
        const SizedBox(height: 20),
        if (detail.hasBarcode)
          SizedBox(
            height: 56,
            child: FilledButton.icon(
              onPressed: () => context.go('/coupon/$couponId/barcode'),
              icon: const Icon(Icons.qr_code_2_outlined),
              label: const Text('바코드 보기'),
            ),
          ),
        const SizedBox(height: 12),
        if (summary.status == 'REDEEMED')
          _ActionButton(
            label: '사용 완료 취소',
            icon: Icons.undo_outlined,
            onPressed: () => ref.read(detailControllerProvider(couponId).notifier).restore(),
          )
        else if (summary.status != 'ARCHIVED')
          _ActionButton(
            label: '사용 완료',
            icon: Icons.done_all_outlined,
            onPressed: () async {
              final outcome =
                  await ref.read(detailControllerProvider(couponId).notifier).redeem();
              if (context.mounted && outcome == RedeemOutcome.queuedOffline) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('오프라인 상태예요 — 연결되면 사용 완료로 동기화됩니다.'),
                  ),
                );
              }
            },
          ),
        const SizedBox(height: 8),
        if ((summary.status == 'ACTIVE' || summary.status == 'EXPIRING_SOON') &&
            detail.hasBarcode)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: _ActionButton(
              label: '마켓에 판매 등록',
              icon: Icons.storefront_outlined,
              onPressed: () => _listForSale(context, ref),
            ),
          ),
        if (summary.status == 'ARCHIVED')
          _ActionButton(
            label: '보관 해제',
            icon: Icons.unarchive_outlined,
            onPressed: () => ref.read(detailControllerProvider(couponId).notifier).unarchive(),
          )
        else
          _ActionButton(
            label: '보관',
            icon: Icons.archive_outlined,
            onPressed: () => ref.read(detailControllerProvider(couponId).notifier).archive(),
          ),
        const SizedBox(height: 8),
        _ActionButton(
          label: '삭제',
          icon: Icons.delete_outline,
          destructive: true,
          onPressed: () async {
            final confirmed = await showDialog<bool>(
              context: context,
              builder: (context) => AlertDialog(
                title: const Text('쿠폰을 삭제할까요?'),
                content: const Text('원본 이미지를 포함해 완전히 삭제되며 되돌릴 수 없어요.'),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(false),
                    child: const Text('취소'),
                  ),
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(true),
                    child: const Text('삭제'),
                  ),
                ],
              ),
            );
            if (confirmed == true) {
              await ref.read(detailControllerProvider(couponId).notifier).delete();
              if (context.mounted) context.go('/wallet');
            }
          },
        ),
      ],
    );
  }

  /// 판매 등록 (M4): price prompt → listing. The dialog states clearly that
  /// the market is mock-paid; server-side eligibility errors show verbatim.
  Future<void> _listForSale(BuildContext context, WidgetRef ref) async {
    final controller = TextEditingController();
    final price = await showDialog<int>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('판매 가격 (원)'),
        content: TextField(
          controller: controller,
          keyboardType: TextInputType.number,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: '예: 4000',
            helperText: '테스트 마켓 — 결제는 모의(MOCK) 처리돼요',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(null),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(int.tryParse(controller.text.trim())),
            child: const Text('등록'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (price == null) return;
    try {
      await ref.read(marketApiProvider).createListing(couponId, price);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('마켓에 등록했어요. 판매 중에는 사용·삭제가 잠깁니다.')),
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

  static String _formatAmount(int amount) {
    final digits = amount.toString();
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(',');
      buffer.write(digits[i]);
    }
    return buffer.toString();
  }
}

String statusLabel(String status) => switch (status) {
      'ACTIVE' => '사용 가능',
      'EXPIRING_SOON' => '곧 만료',
      'EXPIRED' => '만료',
      'REDEEMED' => '사용 완료',
      'NEEDS_REVIEW' => '확인 필요',
      'ARCHIVED' => '보관됨',
      'INVALID' => '인식 실패',
      _ => '처리 중',
    };

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(label, style: const TextStyle(color: AmcColors.textSecondary)),
          ),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.label,
    required this.icon,
    required this.onPressed,
    this.destructive = false,
  });

  final String label;
  final IconData icon;
  final Future<void> Function() onPressed;
  final bool destructive;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: OutlinedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon, color: destructive ? AmcColors.danger : null),
        label: Text(
          label,
          style: destructive ? const TextStyle(color: AmcColors.danger) : null,
        ),
      ),
    );
  }
}

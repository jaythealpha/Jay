import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_theme.dart';
import '../../../core/errors/app_exception.dart';
import '../../../shared/models/coupon_detail.dart';
import '../application/review_controller.dart';
import 'confidence_badge.dart';

/// Confirm, Do Not Type: the system fills what it recognized, the user only
/// verifies or corrects. Low-trust fields are labeled, never silently saved.
class ReviewScreen extends ConsumerWidget {
  const ReviewScreen({super.key, required this.couponId});

  final String couponId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(reviewControllerProvider(couponId));

    return Scaffold(
      appBar: AppBar(title: const Text('인식 결과 확인')),
      body: state.when(
        loading: () => const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('쿠폰을 분석하고 있어요...'),
            ],
          ),
        ),
        error: (error, _) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 48, color: AmcColors.danger),
              const SizedBox(height: 12),
              Text(
                error is AppException ? error.userMessage : '분석 결과를 불러오지 못했어요.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              SizedBox(
                height: 48,
                child: FilledButton(
                  onPressed: () => ref.invalidate(reviewControllerProvider(couponId)),
                  child: const Text('다시 시도'),
                ),
              ),
            ],
          ),
        ),
        data: (detail) => _ReviewForm(couponId: couponId, detail: detail),
      ),
    );
  }
}

class _ReviewForm extends ConsumerStatefulWidget {
  const _ReviewForm({required this.couponId, required this.detail});

  final String couponId;
  final CouponDetail detail;

  @override
  ConsumerState<_ReviewForm> createState() => _ReviewFormState();
}

class _ReviewFormState extends ConsumerState<_ReviewForm> {
  late final TextEditingController _brand;
  late final TextEditingController _product;
  late final TextEditingController _expires;
  late final TextEditingController _amount;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final summary = widget.detail.summary;
    _brand = TextEditingController(text: summary.brandName ?? '');
    _product = TextEditingController(text: summary.productName ?? '');
    _expires = TextEditingController(
      text: summary.expiresAt == null
          ? ''
          : summary.expiresAt!.toIso8601String().substring(0, 10),
    );
    _amount = TextEditingController(text: summary.faceValueMinor?.toString() ?? '');
  }

  @override
  void dispose() {
    _brand.dispose();
    _product.dispose();
    _expires.dispose();
    _amount.dispose();
    super.dispose();
  }

  Map<String, Object?> _changedFields() {
    final summary = widget.detail.summary;
    final fields = <String, Object?>{};
    String? emptyAsNull(String value) => value.trim().isEmpty ? null : value.trim();

    if (emptyAsNull(_brand.text) != summary.brandName) {
      fields['brandName'] = emptyAsNull(_brand.text);
    }
    if (emptyAsNull(_product.text) != summary.productName) {
      fields['productName'] = emptyAsNull(_product.text);
    }
    final currentExpires =
        summary.expiresAt?.toIso8601String().substring(0, 10);
    if (emptyAsNull(_expires.text) != currentExpires) {
      fields['expiresAt'] = emptyAsNull(_expires.text);
    }
    final amountValue = int.tryParse(_amount.text.trim());
    if (amountValue != summary.faceValueMinor) {
      fields['faceValueMinor'] = _amount.text.trim().isEmpty ? null : amountValue;
    }
    return fields;
  }

  Future<void> _save({required bool confirmAfter}) async {
    setState(() => _saving = true);
    final notifier = ref.read(reviewControllerProvider(widget.couponId).notifier);
    final fields = _changedFields();
    if (fields.isNotEmpty) {
      await notifier.saveEdits(fields);
    }
    if (confirmAfter) {
      await notifier.confirmAsCorrect();
    }
    if (mounted) {
      setState(() => _saving = false);
      if (confirmAfter) context.go('/wallet');
    }
  }

  @override
  Widget build(BuildContext context) {
    final detail = widget.detail;
    final confidences = detail.confidences;
    final isInvalid = detail.summary.status == 'INVALID';
    final needsReview = detail.summary.status == 'NEEDS_REVIEW';

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (isInvalid)
          const _Notice(
            icon: Icons.image_not_supported_outlined,
            color: AmcColors.danger,
            text: '쿠폰 정보를 인식하지 못했어요. 아래에 직접 입력하거나 다른 이미지로 다시 등록해 주세요.',
          ),
        if (detail.recognitionError != null)
          const _Notice(
            icon: Icons.warning_amber_outlined,
            color: AmcColors.statusExpiringSoon,
            text: '자동 분석에 실패했어요. 내용을 직접 입력해 주세요.',
          ),
        if (detail.duplicateSuspects.isNotEmpty)
          const _Notice(
            icon: Icons.copy_all_outlined,
            color: AmcColors.statusNeedsReview,
            text: '이미 등록된 쿠폰과 비슷해요. 쿠폰함에서 기존 쿠폰을 확인해 보세요.',
          ),
        if (detail.hasBarcode)
          _Notice(
            icon: Icons.qr_code_2_outlined,
            color: AmcColors.statusActive,
            text: '바코드를 인식했어요 (${detail.barcodeType ?? '형식 미상'}). 안전하게 암호화해 보관합니다.',
          ),
        _Field(label: '브랜드', controller: _brand, confidence: confidences?.brand),
        _Field(label: '상품명', controller: _product, confidence: confidences?.productName),
        _Field(
          label: '유효기간 (YYYY-MM-DD)',
          controller: _expires,
          confidence: confidences?.expiresAt,
          keyboardType: TextInputType.datetime,
        ),
        _Field(
          label: '금액 (원)',
          controller: _amount,
          confidence: confidences?.amountMinor,
          keyboardType: TextInputType.number,
        ),
        const SizedBox(height: 24),
        SizedBox(
          height: 52,
          child: FilledButton(
            onPressed: _saving ? null : () => _save(confirmAfter: needsReview || isInvalid),
            child: Text(needsReview || isInvalid ? '저장하고 확정' : '수정 내용 저장'),
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 48,
          child: TextButton(
            onPressed: _saving ? null : () => context.go('/wallet'),
            child: const Text('쿠폰함으로 이동'),
          ),
        ),
      ],
    );
  }
}

class _Field extends StatelessWidget {
  const _Field({
    required this.label,
    required this.controller,
    required this.confidence,
    this.keyboardType,
  });

  final String label;
  final TextEditingController controller;
  final double? confidence;
  final TextInputType? keyboardType;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
              ConfidenceBadge(confidence: confidence),
            ],
          ),
          const SizedBox(height: 6),
          TextField(
            controller: controller,
            keyboardType: keyboardType,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              isDense: true,
            ),
          ),
        ],
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.icon, required this.color, required this.text});

  final IconData icon;
  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AmcColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AmcColors.border),
      ),
      child: Row(
        children: [
          Icon(icon, color: color),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13))),
        ],
      ),
    );
  }
}

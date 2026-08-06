import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/app_exception.dart';
import '../../../shared/models/coupon_detail.dart';
import '../data/coupon_detail_api.dart';

const _pollInterval = Duration(seconds: 1);
const _pollTimeout = Duration(seconds: 30);

/// Loads a coupon and, while the server is still analyzing (PROCESSING),
/// keeps polling until a terminal status or timeout. Editing and confirming
/// re-emit fresh detail state.
class ReviewController extends AsyncNotifier<CouponDetail> {
  ReviewController(this.couponId);

  final String couponId;

  @override
  Future<CouponDetail> build() async {
    final api = ref.watch(couponDetailApiProvider);
    final deadline = DateTime.now().add(_pollTimeout);

    var detail = await api.fetchDetail(couponId);
    while (detail.isProcessing) {
      if (DateTime.now().isAfter(deadline)) {
        throw const ServerException(debugDetail: 'analysis timed out');
      }
      await Future<void>.delayed(_pollInterval);
      detail = await api.fetchDetail(couponId);
    }
    return detail;
  }

  Future<void> saveEdits(Map<String, Object?> fields) async {
    final api = ref.read(couponDetailApiProvider);
    state = await AsyncValue.guard<CouponDetail>(() => api.patch(couponId, fields));
  }

  Future<void> confirmAsCorrect() async {
    final api = ref.read(couponDetailApiProvider);
    state = await AsyncValue.guard<CouponDetail>(() => api.confirm(couponId));
  }
}

final reviewControllerProvider =
    AsyncNotifierProvider.family<ReviewController, CouponDetail, String>(
  ReviewController.new,
);

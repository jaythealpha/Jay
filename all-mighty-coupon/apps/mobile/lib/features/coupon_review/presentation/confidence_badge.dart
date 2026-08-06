import 'package:flutter/material.dart';

import '../../../app/theme/app_theme.dart';

/// Trust Over Automation: every auto-filled field shows how much the system
/// trusts it. Icon + label together — never color alone (accessibility).
class ConfidenceBadge extends StatelessWidget {
  const ConfidenceBadge({super.key, required this.confidence});

  final double? confidence;

  @override
  Widget build(BuildContext context) {
    final (icon, label, color) = switch (confidence) {
      null => (Icons.edit_outlined, '직접 입력 필요', AmcColors.statusNeedsReview),
      >= 0.9 => (Icons.verified_outlined, '자동 인식', AmcColors.statusActive),
      >= 0.7 => (Icons.help_outline, '확인 권장', AmcColors.statusExpiringSoon),
      _ => (Icons.warning_amber_outlined, '확인 필요', AmcColors.danger),
    };

    return Semantics(
      label: '인식 신뢰도: $label',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 12, color: color)),
        ],
      ),
    );
  }
}

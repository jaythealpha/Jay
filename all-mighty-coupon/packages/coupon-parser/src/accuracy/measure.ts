import { extractFaceValue } from '../amounts';
import { matchBrand } from '../brands';
import { extractExpirationDate } from '../dates';
import { DATASET, DatasetSample } from './dataset';

export interface FieldAccuracy {
  correct: number;
  total: number;
  accuracy: number;
  failures: Array<{ id: string; expected: unknown; actual: unknown }>;
}

export interface AccuracyReport {
  sampleCount: number;
  brand: FieldAccuracy;
  expiresAt: FieldAccuracy;
  amountMinor: FieldAccuracy;
}

function score<T>(
  samples: readonly DatasetSample[],
  expected: (s: DatasetSample) => T | null,
  actual: (s: DatasetSample) => T | null,
): FieldAccuracy {
  const failures: FieldAccuracy['failures'] = [];
  let correct = 0;
  for (const sample of samples) {
    const want = expected(sample);
    const got = actual(sample);
    if (want === got) {
      correct += 1;
    } else {
      failures.push({ id: sample.id, expected: want, actual: got });
    }
  }
  return {
    correct,
    total: samples.length,
    accuracy: samples.length === 0 ? 1 : correct / samples.length,
    failures,
  };
}

export function measureAccuracy(samples: readonly DatasetSample[] = DATASET): AccuracyReport {
  return {
    sampleCount: samples.length,
    brand: score(
      samples,
      (s) => s.expected.brand,
      (s) => matchBrand(s.text)?.value ?? null,
    ),
    expiresAt: score(
      samples,
      (s) => s.expected.expiresAt,
      (s) => extractExpirationDate(s.text)?.value ?? null,
    ),
    amountMinor: score(
      samples,
      (s) => s.expected.amountMinor,
      (s) => extractFaceValue(s.text)?.value ?? null,
    ),
  };
}

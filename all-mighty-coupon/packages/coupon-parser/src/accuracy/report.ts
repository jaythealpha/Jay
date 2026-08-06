import { measureAccuracy } from './measure';

/** CLI entry: `npm run accuracy` from the monorepo root. */
const report = measureAccuracy();

function line(name: string, field: { correct: number; total: number; accuracy: number }): string {
  return `${name.padEnd(12)} ${field.correct}/${field.total}  (${(field.accuracy * 100).toFixed(1)}%)`;
}

console.log(`Recognition parser accuracy — ${report.sampleCount} samples`);
console.log(line('brand', report.brand));
console.log(line('expiresAt', report.expiresAt));
console.log(line('amountMinor', report.amountMinor));

for (const [field, data] of Object.entries({
  brand: report.brand,
  expiresAt: report.expiresAt,
  amountMinor: report.amountMinor,
})) {
  for (const failure of data.failures) {
    console.log(
      `  MISS ${field} @ ${failure.id}: expected ${JSON.stringify(failure.expected)}, got ${JSON.stringify(failure.actual)}`,
    );
  }
}

import clsx from 'clsx';

const RISK_LABELS: Record<string, string> = {
  trusted: '可信',
  low: '低风险',
  medium: '中等风险',
  high: '高风险',
  blocked: '已阻止',
  unknown: '未知',
};

interface Props {
  level: string;
  className?: string;
}

export default function RiskBadge({ level, className }: Props) {
  const label = RISK_LABELS[level] ?? level;
  return (
    <span
      className={clsx('risk-badge', `risk-badge--${level}`, className)}
      aria-label={`风险等级: ${label}`}
    >
      {label}
    </span>
  );
}

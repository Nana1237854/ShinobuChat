import { useEffect, useState } from 'react';
import { listCapabilities } from '../api/operations';

type Props = {
  accessToken: string;
};

export function CapabilityPanel({ accessToken }: Props) {
  const [data, setData] = useState<{ capabilities: Array<Record<string, unknown>> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listCapabilities(accessToken)
      .then((d) => setData(d as { capabilities: Array<Record<string, unknown>> }))
      .finally(() => setLoading(false));
  }, [accessToken]);

  if (loading) return <p>Loading capabilities...</p>;
  const caps = data?.capabilities ?? [];
  if (caps.length === 0) return <p>No capabilities registered.</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>Key</th>
          <th>Label</th>
          <th>Risk</th>
          <th>Enabled</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>
        {caps.map((c) => {
          const decision = c.decision as Record<string, unknown> | undefined;
          return (
            <tr key={c.key as string}>
              <td>{c.key as string}</td>
              <td>{c.label as string}</td>
              <td>{c.risk_level as string}</td>
              <td>{decision?.enabled ? 'Y' : 'N'}</td>
              <td>{decision?.reason as string}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

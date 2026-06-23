import { useEffect, useState } from 'react';
import { listJobRuns } from '../api/operations';

type Props = {
  accessToken: string;
};

export function JobRunsPanel({ accessToken }: Props) {
  const [runs, setRuns] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listJobRuns(accessToken)
      .then((data) => setRuns(data as Array<Record<string, unknown>>))
      .finally(() => setLoading(false));
  }, [accessToken]);

  if (loading) return <p>Loading jobs...</p>;
  if (runs.length === 0) return <p>No job runs recorded.</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>Job</th>
          <th>Status</th>
          <th>Started</th>
          <th>Duration (ms)</th>
          <th>Summary</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.id as string}>
            <td>{r.job_name as string}</td>
            <td>{r.status as string}</td>
            <td>{r.started_at as string}</td>
            <td>{r.duration_ms as number}</td>
            <td>{(r.result_summary as string) || (r.error_message as string) || '-'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

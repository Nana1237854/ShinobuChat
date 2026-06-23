import { useEffect, useState } from 'react';
import { listSkillRuns } from '../api/operations';

type Props = {
  accessToken: string;
};

export function SkillRunsPanel({ accessToken }: Props) {
  const [runs, setRuns] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSkillRuns(accessToken)
      .then((data) => setRuns(data as Array<Record<string, unknown>>))
      .finally(() => setLoading(false));
  }, [accessToken]);

  if (loading) return <p>Loading skill runs...</p>;
  if (runs.length === 0) return <p>No skill runs recorded.</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>Skill</th>
          <th>Trigger</th>
          <th>Matched</th>
          <th>Activated</th>
          <th>Input</th>
          <th>Duration (ms)</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.id as string}>
            <td>{r.skill_name as string}</td>
            <td>{r.trigger_source as string}</td>
            <td>{r.matched ? 'Y' : 'N'}</td>
            <td>{r.activated ? 'Y' : 'N'}</td>
            <td>{(r.input_summary as string)?.slice(0, 60)}</td>
            <td>{r.duration_ms as number}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
